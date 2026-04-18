# AI Speaking Agent

An automated speaking assessment agent that parses web-based practice modules, generates human-like responses using Large Language Models (Gemini, SambaNova, or OpenAI), and synthetically speaks into the browser microphone via text-to-speech.

## Features
- Headless / visible browser automation using Playwright.
- Extracts `SCRIPTED` or `EXTEMPORE` prompts directly from the assessment DOM.
- Generates extempore speeches on the fly using Gemini, Llama 3 (via SambaNova), or GPT-4o-mini (via OpenAI).
- Synthesizes highly natural audio streams using Microsoft Edge TTS.
- Automatically maps a virtual fake audio device to speak directly into the browser assessment portal without manual microphone input.
- Fully auto-advances through the grid interface.

## Prerequisites (Linux)

This bot relies on `ffmpeg` to manipulate the synthetic audio, and Python 3 to run the automation logic.

1. **Install System Dependencies (FFmpeg):**
   ```bash
   # Debian / Ubuntu
   sudo apt-get update
   sudo apt-get install ffmpeg

   # RHEL / Fedora
   sudo dnf install ffmpeg
   ```

2. **Install Python Packages:**
   ```bash
   pip3 install playwright edge-tts google-genai openai
   ```

3. **Install Playwright Browsers:**
   ```bash
   playwright install chromium
   ```

## Configuration

Before running the agent, you must create a local configuration file with your login credentials and the specific target URL where the lesson practice module is located. 


1. Open `config.json` in any text editor and fill in the details:
   
   ```json
   {
       "URL": "https://corporate.bharatenglish.org/#/practice/.../...(remember to paste link in which the practice icon appears)",
       "USERNAME": "your_email@domain.com",
       "PASSWORD": "your_password"
   }
   ```
  

## Usage

1. Start the agent:
   ```bash
   python3 agent.py
   ```

2. The application will prompt you to choose an AI provider to utilize for generating EXTEMPORE answers. Type `1` for Gemini, `2` for SambaNova, or `3` for OpenAI. 
3. If you have not set it as a system environment variable, the terminal will prompt you to paste your relevant API key (`GEMINI_API_KEY`, `SAMBANOVA_API_KEY`, or `OPENAI_API_KEY`).
4. The Chromium browser will launch visibly, automatically log in, find the practice grid, and execute the speaking tests completely hands-free!



## For any Query : 
   Contact me on linkedin : https://www.linkedin.com/in/aviral-aviral-495394259/
