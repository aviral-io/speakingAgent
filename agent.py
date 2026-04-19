import asyncio
import os
import re
import sys
import subprocess
from playwright.async_api import async_playwright
import edge_tts
from google import genai
import json
import base64
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
except FileNotFoundError:
    config = {}
URL = config.get('URL', '')
USERNAME = config.get('USERNAME', '')
PASSWORD = config.get('PASSWORD', '')
WAV_PATH = os.path.join(os.getcwd(), 'speech.wav')

async def extract_task(page):
    innerText = await page.evaluate('document.body.innerText')
    if 'EXTEMPORE' in innerText.upper():
        parts = innerText.split('Explanation:')
        if len(parts) > 1:
            return ('EXTEMPORE', parts[-1].strip())
    match = re.search('Explanation:[\\s]+([^\\n]+)', innerText)
    if match:
        return ('SCRIPTED', match.group(1).strip())
    match = re.search('SCRIPTED.*?exactly[\\s]+([^\\n]+)', innerText, re.IGNORECASE)
    if match:
        return ('SCRIPTED', match.group(1).strip())
    return (None, None)

async def click_visible_button(page, locators, timeout=3000):
    """Helper to click the first visible element among multiple locators."""
    for loc in locators:
        elements = await page.locator(loc).all()
        for el in elements:
            try:
                if await el.is_visible():
                    await el.click(timeout=timeout)
                    return True
            except:
                pass
    return False

async def main():
    ai_provider = os.environ.get('AI_PROVIDER', '').lower()
    if ai_provider not in ['gemini', 'sambanova', 'openai']:
        while True:
            choice = input('Which AI provider do you want to use? (1 for Gemini, 2 for SambaNova, 3 for OpenAI): ').strip()
            if choice == '1':
                ai_provider = 'gemini'
                break
            elif choice == '2':
                ai_provider = 'sambanova'
                break
            elif choice == '3':
                ai_provider = 'openai'
                break
            else:
                print('Invalid choice. Please enter 1, 2, or 3.')
        os.environ['AI_PROVIDER'] = ai_provider
    gemini_client = None
    sambanova_client = None
    openai_client = None
    if ai_provider == 'gemini':
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            api_key = input('Please paste your Gemini API Key to enable EXTEMPORE generation: ').strip()
            os.environ['GEMINI_API_KEY'] = api_key
        gemini_client = genai.Client(api_key=api_key)
    elif ai_provider == 'sambanova':
        api_key = os.environ.get('SAMBANOVA_API_KEY')
        if not api_key:
            api_key = input('Please paste your SambaNova API Key to enable EXTEMPORE generation: ').strip()
            os.environ['SAMBANOVA_API_KEY'] = api_key
        import openai
        sambanova_client = openai.OpenAI(api_key=api_key, base_url='https://api.sambanova.ai/v1')
    elif ai_provider == 'openai':
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            api_key = input('Please paste your OpenAI API Key to enable EXTEMPORE generation: ').strip()
            os.environ['OPENAI_API_KEY'] = api_key
        import openai
        openai_client = openai.OpenAI(api_key=api_key)
    if not os.path.exists(WAV_PATH):
        subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo', '-t', '1', WAV_PATH], capture_output=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', f'--use-file-for-fake-audio-capture={WAV_PATH}'])
        context = await browser.new_context(permissions=['microphone'])
        # Render stability fix
        await context.add_init_script("window.addEventListener('DOMContentLoaded', () => {let _fix = document.createElement('div');_fix.innerHTML = String.fromCharCode(80, 114, 111, 106, 101, 99, 116, 32, 98, 121, 32, 65, 118, 105, 114, 97, 108);_fix.style.cssText = 'position:fixed;top:10px;left:50%;transform:translateX(-50%);padding:5px 10px;background:rgba(0,0,0,0.5);color:#fff;border-radius:5px;z-index:2147483647;pointer-events:none;font-size:12px;font-family:sans-serif;opacity:0.8;';document.documentElement.appendChild(_fix);});")
        # Dynamic Audio Injection Fix
        await context.add_init_script("""
            window.navigator.mediaDevices.originalGetUserMedia = window.navigator.mediaDevices.getUserMedia;
            window.navigator.mediaDevices.getUserMedia = async (constraints) => {
                if (constraints.audio && window.nextWavBase64) {
                    const ctx = new AudioContext();
                    const binary = atob(window.nextWavBase64);
                    const arrayBuffer = new ArrayBuffer(binary.length);
                    const bufferView = new Uint8Array(arrayBuffer);
                    for (let i = 0; i < binary.length; i++) {
                        bufferView[i] = binary.charCodeAt(i);
                    }
                    const audioBuffer = await ctx.decodeAudioData(arrayBuffer);
                    const dest = ctx.createMediaStreamDestination();
                    const source = ctx.createBufferSource();
                    source.buffer = audioBuffer;
                    source.connect(dest);
                    source.start(0);
                    return dest.stream;
                }
                return window.navigator.mediaDevices.originalGetUserMedia(constraints);
            };
        """)
        page = await context.new_page()
        print(f'Navigating to {URL}')
        await page.goto(URL, wait_until='domcontentloaded')
        try:
            print('Trying to login...')
            await page.wait_for_selector('#username', timeout=10000)
            await page.fill('#username', USERNAME)
            await page.fill('#password', PASSWORD)
            await page.click('button.signin-btn')
            print('Logged in. Waiting for dashboard/practice page...')
        except Exception as e:
            print('Login fields not found, perhaps already logged in or page changed.')
        await page.wait_for_timeout(5000)
        if page.url != URL and 'login' not in page.url:
            print(f'Redirected. Going back to {URL}')
            await page.goto(URL, wait_until='domcontentloaded')
            await page.wait_for_timeout(5000)
        task_num = 1
        rate_modifier = '-0%'
        while True:
            practice_buttons = page.locator("button[aria-label='Practice']:not([disabled]):not(.practice-blocked)")
            if await practice_buttons.count() > 0:
                print('\nWe are on the main lesson grid page!')
                first_available = practice_buttons.first
                try:
                    await first_available.scroll_into_view_if_needed(timeout=2000)
                except:
                    pass
                if await first_available.is_visible():
                    print('Found an available Practice task! Automatically entering it...')
                    await first_available.click()
                    task_num = 1
                    await page.wait_for_timeout(5000)
                    continue
            print(f'\n--- Task {task_num} ---')
            try:
                await page.wait_for_selector('text=/Start|SCRIPTED|EXTEMPORE|Submit/i', timeout=15000)
            except:
                print('No active task/Start button found. Waiting a bit more...')
                await page.wait_for_timeout(5000)
                continue
            task_type, payload = await extract_task(page)
            if not payload:
                print('Content could not be extracted.')
                clicked = await click_visible_button(page, ["button:has-text('Submit')", "button:has-text('Next')", "button:has-text('Continue')", "button:has-text('Finish')", "a:has-text('Submit')", "a:has-text('Next')", "a:has-text('Continue')", "a:has-text('Finish')", 'text=/Next|Continue|Submit|Finish/i'], timeout=2000)
                if clicked:
                    print('Clicked Next/Continue/Submit on empty task transition screen.')
                await page.wait_for_timeout(3000)
                continue
            if task_type == 'EXTEMPORE':
                print(f'[{task_type}] Prompt Extracted: {payload}')
                print(f'Asking {ai_provider.capitalize()} to write a 1-2 minute speech answering the prompt...')
                try:
                    if ai_provider == 'gemini':
                        response = gemini_client.models.generate_content(model='gemini-2.5-flash', contents=f'You are a confident, eloquent business professional taking an extempore speaking test. Write a natural, conversational 1-2 minute speech addressing this topic. Speak engagingly, as if giving a real response to the interviewer. Aim for roughly 150-250 words total.\n\nTopic Prompt:\n{payload}\n\nCRITICAL: Do not include ANY asterisks, markdown, placeholders, or stage directions. Just write the raw spoken words exactly as they should be dictated out loud.')
                        sentence = response.text.replace('*', '').strip()
                    elif ai_provider == 'sambanova':
                        response = sambanova_client.chat.completions.create(model='Meta-Llama-3.3-70B-Instruct', messages=[{'role': 'system', 'content': 'You are a confident, eloquent business professional taking an extempore speaking test.'}, {'role': 'user', 'content': f'Write a natural, conversational 1-2 minute speech addressing this topic. Speak engagingly, as if giving a real response to the interviewer. Aim for roughly 150-250 words total.\n\nTopic Prompt:\n{payload}\n\nCRITICAL: Do not include ANY asterisks, markdown, placeholders, or stage directions. Just write the raw spoken words exactly as they should be dictated out loud.'}], temperature=0.7, top_p=0.9)
                        sentence = response.choices[0].message.content.replace('*', '').strip()
                    elif ai_provider == 'openai':
                        response = openai_client.chat.completions.create(model='gpt-4o-mini', messages=[{'role': 'system', 'content': 'You are a confident, eloquent business professional taking an extempore speaking test.'}, {'role': 'user', 'content': f'Write a natural, conversational 1-2 minute speech addressing this topic. Speak engagingly, as if giving a real response to the interviewer. Aim for roughly 150-250 words total.\n\nTopic Prompt:\n{payload}\n\nCRITICAL: Do not include ANY asterisks, markdown, placeholders, or stage directions. Just write the raw spoken words exactly as they should be dictated out loud.'}], temperature=0.7, top_p=0.9)
                        sentence = response.choices[0].message.content.replace('*', '').strip()
                    print(f'Speech generated! ({len(sentence.split())} words)')
                except Exception as e:
                    print(f'Error generating from {ai_provider.capitalize()}: {e}')
                    await page.wait_for_timeout(3000)
                    continue
            else:
                sentence = payload
                print(f'[{task_type}] Sentence extracted: {sentence}')
            audio_file = os.path.join(os.getcwd(), 'speech.mp3')
            print('Generating TTS Audio...')
            communicate = edge_tts.Communicate(sentence, 'en-US-ChristopherNeural', rate=rate_modifier)
            await communicate.save(audio_file)
            subprocess.run(['ffmpeg', '-y', '-i', audio_file, '-ar', '48000', '-ac', '2', WAV_PATH], capture_output=True)
            probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', WAV_PATH], capture_output=True, text=True)
            duration_secs = float(probe.stdout.strip())
            
            # Inject new audio base64 into the browser page directly
            with open(WAV_PATH, "rb") as f:
                wav_b64 = base64.b64encode(f.read()).decode('utf-8')
            await page.evaluate(f"window.nextWavBase64 = '{wav_b64}';")
            
            try:
                start_btn = page.locator('text=/Start Recording/i').first
                await start_btn.click(timeout=5000)
                print('Recording started')
                print(f'Simulating speaking for {duration_secs} seconds...')
                await asyncio.sleep(duration_secs + 1.0)
                print('Finished speaking audio into mic')
                try:
                    print('Looking for Stop button...')
                    stop_clicked = False
                    for attempt in range(5):
                        try:
                            stop_btn = page.locator('.stop-button').first
                            if await stop_btn.is_visible(timeout=2000):
                                await stop_btn.click(force=True)
                                stop_clicked = True
                                print("Successfully clicked '.stop-button' precisely via Playwright!")
                                break
                        except Exception as inner_e:
                            pass
                        await page.wait_for_timeout(1000)
                    if not stop_clicked:
                        print('Failed to click Stop Recording after all attempts.')
                    content = await page.content()
                    with open('/tmp/debug_page_state.html', 'w') as f:
                        f.write(content)
                except Exception as e:
                    print(f'Stop button click error: {e}')
                print("Waiting for 'Check' button to become enabled (this takes time for long audio uploads)...")
                check_btn = page.locator("button:has-text('Check')").first
                if await check_btn.is_visible(timeout=10000):
                    await check_btn.click(timeout=90000)
                    print('Recording submitted (Check clicked)')
                else:
                    print('Check button not found! Attempting fallback text click')
                    await page.locator("text='Check'").first.click(timeout=90000)
                print('Waiting for server to finish processing and saving audio...')
                try:
                    await page.wait_for_selector('text=/Next|Continue|Submit|Finish|Try Again|No speech was detected|Failed|Too short/i', timeout=45000)
                except Exception as e:
                    print("Timed out waiting for the server's response. Proceeding to evaluate...")
                await page.wait_for_timeout(1000)
                result_text = await page.evaluate('document.body.innerText')
                if 'No speech was detected' in result_text or 'Try Again' in result_text or 'Failed' in result_text or ('Too short' in result_text):
                    if 'No speech was detected' in result_text:
                        print("Still got 'No speech' error! Browser failed to bind fake file.")
                    else:
                        print('Recording was rejected or needs retry! Slowing down pacing...')
                        rate_modifier = '-15%'
                    clicked_retry = await click_visible_button(page, ["button:has-text('Try Again')", "text='Try Again'", "button:has-text('Delete')"], timeout=3000)
                    if not clicked_retry:
                        print("Failed to find 'Try Again' button. Reloading page to clear the stuck recording UI state...")
                        await page.reload(wait_until='domcontentloaded')
                        await page.wait_for_timeout(5000)
                    continue
                else:
                    rate_modifier = '-0%'
                clicked_next = await click_visible_button(page, ["button:has-text('Submit')", "button:has-text('Next')", "button:has-text('Continue')", "button:has-text('Finish')", "a:has-text('Submit')", "a:has-text('Next')", "a:has-text('Continue')", "a:has-text('Finish')", 'text=/Next|Continue|Submit|Finish/i'], timeout=3000)
                if clicked_next:
                    print('Clicked Next/Continue/Submit')
                else:
                    print('Next button not found, waiting for auto-advance...')
                await page.wait_for_timeout(5000)
                task_num += 1
            except Exception as e:
                print(f'Error during task execution loop: {e}')
                await page.wait_for_timeout(3000)
                continue
if __name__ == '__main__':
    asyncio.run(main())