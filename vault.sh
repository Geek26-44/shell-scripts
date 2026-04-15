#!/bin/bash
# Secure Vault — локальное хранилище паролей с GPG шифрованием

VAULT_DIR="/Users/geek2026/.openclaw/workspace/vault"
VAULT_FILE="$VAULT_DIR/passwords.gpg"
TEMP_DIR="/tmp/vault-$$"

mkdir -p "$VAULT_DIR"

# Инициализация vault
init_vault() {
    echo "=== Secure Vault Initialization ==="
    echo ""

    if [ -f "$VAULT_FILE" ]; then
        echo "Vault already exists: $VAULT_FILE"
        return 1
    fi

    echo "Creating new vault..."
    echo "# Secure Password Vault" | gpg --symmetric --cipher-algo AES256 -o "$VAULT_FILE"

    echo ""
    echo "✓ Vault created: $VAULT_FILE"
    echo ""
    echo "SECURITY NOTES:"
    echo "  - Choose a STRONG master password"
    echo "  - This password CANNOT be recovered"
    echo "  - Store it in memory or write down securely"
}

# Добавить пароль
add_password() {
    local service="$1"
    local username="$2"
    local password="$3"

    # Расшифровать vault
    mkdir -p "$TEMP_DIR"
    gpg -d "$VAULT_FILE" > "$TEMP_DIR/vault.txt" 2>/dev/null

    # Добавить запись
    echo "" >> "$TEMP_DIR/vault.txt"
    echo "=== $service ===" >> "$TEMP_DIR/vault.txt"
    echo "Username: $username" >> "$TEMP_DIR/vault.txt"
    echo "Password: $password" >> "$TEMP_DIR/vault.txt"
    echo "Created: $(date '+%Y-%m-%d %H:%M')" >> "$TEMP_DIR/vault.txt"

    # Зашифровать обратно
    gpg --symmetric --cipher-algo AES256 -o "$VAULT_FILE" "$TEMP_DIR/vault.txt"

    # Очистить временные файлы
    rm -rf "$TEMP_DIR"

    echo "✓ Password saved for: $service"
}

# Получить пароль
get_password() {
    local service="$1"

    gpg -d "$VAULT_FILE" 2>/dev/null | grep -A 10 "=== $service ==="
}

# Список всех сервисов
list_services() {
    echo "=== Stored Services ==="
    gpg -d "$VAULT_FILE" 2>/dev/null | grep "^===" | sed 's/=== //;s/ ===//'
}

# Удалить сервис
delete_service() {
    local service="$1"

    mkdir -p "$TEMP_DIR"
    gpg -d "$VAULT_FILE" > "$TEMP_DIR/vault.txt" 2>/dev/null

    # Удалить записи сервиса
    grep -v "=== $service ===" "$TEMP_DIR/vault.txt" | grep -v "^Username:" | grep -v "^Password:" | grep -v "^Created:" | grep -v "^$" > "$TEMP_DIR/vault-new.txt"

    gpg --symmetric --cipher-algo AES256 -o "$VAULT_FILE" "$TEMP_DIR/vault-new.txt"
    rm -rf "$TEMP_DIR"

    echo "✓ Deleted: $service"
}

# Командная строка
case "$1" in
    init)
        init_vault
        ;;
    add)
        if [ -z "$3" ]; then
            echo "Usage: $0 add <service> <username>"
            echo "Password will be prompted"
            read -s -p "Password: " password
            echo ""
            add_password "$2" "$3" "$password"
        else
            add_password "$2" "$3" "$4"
        fi
        ;;
    get)
        get_password "$2"
        ;;
    list)
        list_services
        ;;
    delete)
        delete_service "$2"
        ;;
    *)
        echo "Secure Vault — Password Manager"
        echo ""
        echo "Usage: $0 <command> [args]"
        echo ""
        echo "Commands:"
        echo "  init                  — initialize vault"
        echo "  add <service> <user>  — add password (prompted)"
        echo "  get <service>         — retrieve password"
        echo "  list                  — list all services"
        echo "  delete <service>      — delete service"
        echo ""
        echo "Vault: $VAULT_FILE"
        echo "Encryption: AES-256 GPG"
        ;;
esac
