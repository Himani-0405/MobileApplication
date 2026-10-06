# 🚀 Mobile FoodBridge — Deployment & Android APK Generation Guide

This guide provides step-by-step instructions to **deploy your Python Flask backend live to the cloud** and **generate the Android APK file (`.apk`)** for your mobile application.

---

## 🛠️ Step 1: Cloud Deployment (Live Backend Server)

Your Flask application is pre-configured with `gunicorn`, `Procfile`, `wsgi.py`, `Dockerfile`, and `render.yaml`.

### Option A: Deploy to Render.com (Recommended Free Hosting)
1. Push your repository to GitHub.
2. Go to [Render.com](https://render.com) and create a free account.
3. Click **New +** -> **Web Service**.
4. Connect your GitHub repository `Mobile_FoodBridge`.
5. Render will automatically detect `render.yaml` or set:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn wsgi:app --bind 0.0.0.0:$PORT`
6. Click **Create Web Service**. Within 2 minutes, your live URL will be ready (e.g., `https://mobile-foodbridge.onrender.com`).

### Option B: Deploy with Docker (Render / Koyeb / Fly.io / AWS)
Build and run the Docker image anywhere:
```bash
docker build -t mobile-foodbridge .
docker run -p 5000:5000 mobile-foodbridge
```

---

## 📱 Step 2: Generate the Android APK File (`.apk`)

We have set up **3 methods** to create the `.apk` file for your app:

### Method 1: Automatic APK Generation via GitHub Actions (Easiest & Fastest ⚡)
1. Push this project to your GitHub repository.
2. Go to the **Actions** tab on your GitHub repository page.
3. Click on the **Build Android APK** workflow and click **Run workflow**.
4. GitHub Actions will automatically compile the Android app and provide a downloadable **`FoodBridge-Mobile-v1.0.apk`** artifact!

---

### Method 2: Open & Build in Android Studio
1. Open [Android Studio](https://developer.android.com/studio).
2. Click **Open an existing project** and select the [`android-project`](file:///c:/Users/LENOVO/Desktop/Mobile_FoodBridge/android-project) folder inside this repository.
3. Update `SERVER_URL` in [`MainActivity.java`](file:///c:/Users/LENOVO/Desktop/Mobile_FoodBridge/android-project/app/src/main/java/com/foodbridge/mobile/MainActivity.java) with your deployed server URL.
4. Go to **Build** -> **Build Bundle(s) / APK(s)** -> **Build APK(s)**.
5. Android Studio will generate `app-debug.apk` in `android-project/app/build/outputs/apk/debug/`.

---

### Method 3: Command Line Gradle Build (Local Machine)
If Java & Android SDK are configured on your computer:
```powershell
.\build-apk.ps1
```
Or manually run:
```bash
cd android-project
./gradlew assembleDebug
```
The output APK file will be located at:
`android-project/app/build/outputs/apk/debug/app-debug.apk`

---

## 📁 Prepared Project Files Summary

| File Path | Description |
| :--- | :--- |
| [`requirements.txt`](file:///c:/Users/LENOVO/Desktop/Mobile_FoodBridge/requirements.txt) | Updated with `gunicorn` for cloud deployment |
| [`Procfile`](file:///c:/Users/LENOVO/Desktop/Mobile_FoodBridge/Procfile) | Web server command for Heroku/Render/Railway |
| [`wsgi.py`](file:///c:/Users/LENOVO/Desktop/Mobile_FoodBridge/wsgi.py) | Production WSGI entry point for Flask |
| [`Dockerfile`](file:///c:/Users/LENOVO/Desktop/Mobile_FoodBridge/Dockerfile) | Container definition for Docker cloud platforms |
| [`render.yaml`](file:///c:/Users/LENOVO/Desktop/Mobile_FoodBridge/render.yaml) | Render 1-click cloud deployment spec |
| [`static/manifest.json`](file:///c:/Users/LENOVO/Desktop/Mobile_FoodBridge/static/manifest.json) | Web App Manifest for mobile PWA support |
| [`capacitor.config.json`](file:///c:/Users/LENOVO/Desktop/Mobile_FoodBridge/capacitor.config.json) | Capacitor cross-platform mobile app config |
| [`android-project/`](file:///c:/Users/LENOVO/Desktop/Mobile_FoodBridge/android-project) | Complete Android Studio Gradle app project |
| [`.github/workflows/build-apk.yml`](file:///c:/Users/LENOVO/Desktop/Mobile_FoodBridge/.github/workflows/build-apk.yml) | Automated GitHub Actions CI workflow to build APK |
| [`build-apk.ps1`](file:///c:/Users/LENOVO/Desktop/Mobile_FoodBridge/build-apk.ps1) | Local Windows PowerShell helper script to compile APK |
