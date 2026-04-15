const { chromium } = require('playwright');

(async () => {
  console.log('🔐 Запускаю браузер для авторизации GitHub...\n');
  
  const browser = await chromium.launch({ 
    headless: false,  // Показываем браузер
    slowMo: 100       // Замедляем для визуального контроля
  });
  
  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 }
  });
  
  const page = await context.newPage();
  
  // Открываем страницу логина
  await page.goto('https://github.com/login');
  
  console.log('⏳ Жду логина...');
  console.log('   1. Введи логин/пароль в браузере');
  console.log('   2. Нажми Sign in');
  console.log('   3. Жди...\n');
  
  // Ждём когда попадём на главную страницу после логина
  await page.waitForURL('https://github.com/**', { timeout: 120000 });
  
  console.log('✅ Успешный логин!\n');
  
  // Сохраняем cookies для будущего использования
  const cookies = await context.cookies();
  require('fs').writeFileSync(
    '/Users/geek2026/.openclaw/workspace/github-cookies.json',
    JSON.stringify(cookies, null, 2)
  );
  console.log('💾 Cookies сохранены\n');
  
  // Теперь идём к репозиториям
  console.log('📋 Открываю репозитории...\n');
  await page.goto('https://github.com/Geek26-44?tab=repositories');
  await page.waitForTimeout(3000);
  
  // Ищем репозитории
  const repos = await page.evaluate(() => {
    const items = [];
    
    // Пробуем разные селекторы
    const selectors = [
      'li[data-testid="repository-list-item"]',
      '.repo-list-item',
      '[itemprop="owns"]',
      'div[id*="repository"]'
    ];
    
    for (const selector of selectors) {
      const elements = document.querySelectorAll(selector);
      if (elements.length > 0) {
        elements.forEach(el => {
          const link = el.querySelector('a[href*="/Geek26-44/"]');
          if (link) {
            const name = link.textContent.trim();
            const href = link.href;
            const desc = el.querySelector('p')?.textContent?.trim() || '';
            const isPrivate = el.textContent.includes('Private');
            
            items.push({
              name,
              href,
              description: desc,
              private: isPrivate
            });
          }
        });
        break;
      }
    }
    
    return items;
  });
  
  if (repos.length > 0) {
    console.log('## 📂 Репозитории Geek26-44\n');
    repos.forEach((repo, i) => {
      const icon = repo.private ? '🔒' : '🌍';
      console.log(`${i + 1}. ${icon} **${repo.name}**`);
      if (repo.description) console.log(`   ${repo.description}`);
      console.log(`   ${repo.href}\n`);
    });
    console.log(`✅ Всего: ${repos.length} репозиториев`);
  } else {
    // Если не нашли через селекторы, парсим текст
    const pageText = await page.evaluate(() => document.body.innerText);
    console.log('📄 Текст со страницы:\n');
    console.log(pageText);
  }
  
  // Скриншот
  await page.screenshot({ 
    path: '/Users/geek2026/Screenshots/Geek/github-private-repos.png',
    fullPage: true 
  });
  console.log('\n📸 Скриншот сохранён');
  
  // Браузер оставляем открытым
  console.log('\n✅ Готово! Браузер оставляю открытым для работы.');
  console.log('   Закрой браузер когда закончишь.\n');
  
  // Не закрываем браузер
  // await browser.close();
})();
