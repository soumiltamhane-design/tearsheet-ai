# Deploy Tearsheet AI to Streamlit Cloud (Free)

This guide takes **3 minutes** and requires **zero coding knowledge**. You'll end up with a live link like `https://tearsheet-ai.streamlit.app` that you can click anytime.

## Step 1 — Create a GitHub account (2 minutes)

1. Go to **github.com**
2. Click the **"Sign up"** button (top-right)
3. Pick a username and password
4. Click through the verification emails if it asks
5. You now have a GitHub account. Done.

## Step 2 — Create a new repository (1 minute)

1. After signing up, you should see a **"+" menu** in the top-right. Click it.
2. Click **"New repository"**
3. In the **"Repository name"** box, type: `tearsheet-ai`
4. Check the box that says **"Add a README file"**
5. Click **"Create repository"** at the bottom
6. You now have an empty repo. Done.

## Step 3 — Upload all the code files (1 minute)

You should be on the repository page now (it says `tearsheet-ai` at the top with your username).

1. Click the **"Add file"** button (top-right, next to a green "Code" button)
2. Click **"Upload files"**
3. A file-picker dialog opens. **Download the `tearsheet_deployed.zip` file** (link below) and unzip it on your computer.
4. From inside that unzipped folder, drag **all the files** into the browser window:
   - `app.py`
   - `quant_engine.py`
   - `scoring_engine.py`
   - `ai_reasoning.py`
   - `data_fetcher.py`
   - `requirements.txt`
   - The entire `sample_data` folder
5. Click **"Commit changes"** at the bottom
6. GitHub now has all your code. Done.

## Step 4 — Deploy to Streamlit Cloud (1 minute)

1. Go to **streamlit.io/cloud** in a new tab
2. Click **"Sign in"** (top-right)
3. Click **"Sign in with GitHub"** — it'll ask permission to read your GitHub repos, click **"Authorize"**
4. You should now see a **"Deploy an app"** section. Click **"New app"**
5. A form appears. Fill it in:
   - **Repository:** `username/tearsheet-ai` (replace `username` with your actual GitHub username)
   - **Branch:** `main`
   - **Main file path:** `app.py`
6. Click **"Deploy"**

Streamlit will now build and deploy your app — this takes about 30 seconds. You'll see a loading bar. When it finishes, you get a **live URL** at the top of the page.

**That URL is your tool.** Bookmark it, share it, use it anytime. No more steps.

## Using the deployed app

1. Click your Streamlit Cloud URL
2. Left sidebar: pick a company from the dropdown
3. Make sure "Free: copy-paste into Claude.ai" is selected under "AI commentary"
4. Click **"Run analysis"**
5. You see your tear sheet immediately
6. If you want the AI write-up, follow the instructions in the "AI reasoning" section (copy/paste into claude.ai, paste the reply back)

That's it. No terminal, no Python on your laptop, no hassle.

---

## Need help?

- **"I don't see a 'Add file' button"** — Make sure you're on your repo page (it should say `username/tearsheet-ai` near the top)
- **"The app shows an error after I deployed"** — Streamlit Cloud can take 1–2 minutes to fully start up. Refresh the page.
- **"I want to change something in the code"** — Edit the file directly on GitHub (click the file, click the pencil icon), and Streamlit Cloud auto-redeploys in ~30 seconds.
