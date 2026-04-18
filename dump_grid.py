import asyncio
from playwright.async_api import async_playwright

async def main():
    URL = "https://corporate.bharatenglish.org/#/practice/16962/lessons/283693?sectionId=2&unitId=48"
    USERNAME = "aviral.25005071@kiet.edu"
    PASSWORD = "Aviral@00"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        print(f"Navigating to {URL}")
        await page.goto(URL, wait_until="domcontentloaded")
        
        try:
            print("Trying to login...")
            await page.wait_for_selector('#username', timeout=10000)
            await page.fill('#username', USERNAME)
            await page.fill('#password', PASSWORD)
            await page.click('button.signin-btn')
            print("Logged in. Waiting for dashboard/practice page...")
        except Exception as e:
            print("Login fields not found, perhaps already logged in or page changed.")

        await page.wait_for_timeout(5000)
        if page.url != URL and "login" not in page.url:
            print(f"Redirected. Going back to {URL}")
            await page.goto(URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)

        await page.wait_for_selector("text=/Let’s begin your practice/i", timeout=15000)
        print("Grid loaded.")
        content = await page.content()
        with open("/tmp/grid_page.html", "w") as f:
            f.write(content)
        print("Saved to /tmp/grid_page.html")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
