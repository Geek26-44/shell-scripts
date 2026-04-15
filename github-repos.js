const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();
  
  console.log('🔍 Открываю GitHub...');
  await page.goto('https://github.com/Geek26-44?tab=repositories', {
    waitUntil: 'domcontentloaded',
    timeout: 30000
  });
  
  // Ждём загрузки контента
  await page.waitForTimeout(3000);
  
  console.log('📋 Ищу репозитории...\n');
  
  // Получаем текст со страницы
  const pageText = await page.evaluate(() => document.body.innerText);
  
  // Ищем названия репозиториев (формат: "repo-name Public/Private")
  const repoMatches = pageText.match(/([a-zA-Z0-9_-]+)\s+(Public|Private)/g);
  
  if (repoMatches) {
    console.log('## 📂 Репозитории Geek26-44\n');
    repoMatches.forEach((match, i) => {
      const [name, visibility] = match.split(/\s+/);
      const icon = visibility === 'Private' ? '🔒' : '🌍';
      console.log(`${i + 1}. ${icon} **${name}** (${visibility})`);
    });
    console.log(`\n✅ Всего: ${repoMatches.length} репозиториев`);
  } else {
    console.log('⚠️ Репозитории не найдены через regex');
    console.log('\n📄 Первые 1000 символов со страницы:\n');
    console.log(pageText.substring(0, 1000));
  }
  
  // Сохраняем скриншот для анализа
  await page.screenshot({ path: '/Users/geek2026/Screenshots/Geek/github-playwright.png', fullPage: false });
  console.log('\n📸 Скриншот сохранён');
  
  await browser.close();
})();
