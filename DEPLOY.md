# 🚀 Deploying NextQuestAI to Hugging Face Spaces

This guide explains how to set up continuous deployment for NextQuestAI from GitHub to Hugging Face Spaces using GitHub Actions.

## 1. Prepare your Hugging Face Space
1. Log in to [Hugging Face](https://huggingface.co/).
2. Click on **New Space**.
3. Name your space (e.g., `NextQuestAI`).
4. Select **Streamlit** as the SDK.
5. Choose **Public** or **Private** (Public is free, but your code will be visible).
6. Click **Create Space**.

## 2. Configure Hugging Face Secrets
Your app requires several API keys to function. You must add these as "Variables" or "Secrets" in your Hugging Face Space:
1. Go to your Space on Hugging Face.
2. Click on **Settings** -> **Variables and secrets**.
3. Add the following secrets:
   - `NVIDIA_API_KEY`: Your Nvidia NIM API key.
   - `SEARCH_PROVIDER`: Set to `duckduckgo` (default) or `serper`.
   - `SERP_API_KEY`: (Optional) If using Serper.
   - `HF_TOKEN`: (Optional) If using HuggingFace models.

## 3. Configure GitHub Secrets
To allow GitHub to push code to Hugging Face, you need a User Access Token:
1. Go to your [Hugging Face Settings -> Tokens](https://huggingface.co/settings/tokens).
2. Create a new **Write** token named `GITHUB_DEPLOY`.
3. Copy the token.
4. Go to your **GitHub Repository** -> **Settings** -> **Secrets and variables** -> **Actions**.
5. Click **New repository secret**.
6. Name: `HF_TOKEN`
7. Value: (Paste your Hugging Face token here)

## 4. Automatic Deployment
The provided GitHub Action in `.github/workflows/huggingface_sync.yml` is now active.
Every time you `git push origin main`, your app will automatically update on Hugging Face Spaces.

## 5. Local Database Note
Note that `nexusai_history.db` is a local SQLite database. On Hugging Face Spaces, data written to the disk is **ephemeral** and will be lost when the Space restarts. For persistent long-term history in production, consider upgrading to a managed PostgreSQL database.
