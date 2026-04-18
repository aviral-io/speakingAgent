import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        url = 'https://corporate.bharatenglish.org/#/practice/16962/lessons/283693?sectionId=2&unitId=48'
        print(f'Navigating to {url}')
        await page.goto(url)
        await page.wait_for_timeout(3000)
        print('Logging in...')
        await page.fill('#username', 'YOUR_EMAIL')
        await page.fill('#password', 'YOUR_PASSWORD')
        await page.click('button.signin-btn')
        print('Waiting for page load after login...')
        await page.wait_for_timeout(10000)
        print(f'Current URL: {page.url}')
        if page.url != url:
            print('Redirected to a different page, navigating back to target URL...')
            await page.goto(url)
            await page.wait_for_timeout(10000)
        content = await page.content()
        with open('practice_page.html', 'w') as f:
            f.write(content)
        await browser.close()
        print('Done. Check practice_page.html')
if __name__ == '__main__':
    asyncio.run(main())