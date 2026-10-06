# ====================================================================
# FoodBridge Mobile — Local & Cloud APK Build Helper Script
# ====================================================================

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "         FoodBridge Mobile APK Builder Helper             " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Green

$androidProjPath = "$PSScriptRoot\android-project"

if (Test-Path "$androidProjPath\gradlew.bat") {
    Write-Host "[+] Navigating to Android Project directory..." -ForegroundColor Yellow
    Set-Location $androidProjPath
    Write-Host "[+] Running Gradle Debug APK Build..." -ForegroundColor Yellow
    .\gradlew.bat assembleDebug
    
    $apkPath = "$androidProjPath\app\build\outputs\apk\debug\app-debug.apk"
    if (Test-Path $apkPath) {
        Write-Host "==========================================================" -ForegroundColor Green
        Write-Host " SUCCESS: APK compiled successfully!" -ForegroundColor Green
        Write-Host " APK File Location: $apkPath" -ForegroundColor Cyan
        Write-Host "==========================================================" -ForegroundColor Green
    } else {
        Write-Host "[-] Build finished. Check output above." -ForegroundColor Yellow
    }
} else {
    Write-Host "[!] Android Gradle wrapper not found locally." -ForegroundColor Red
    Write-Host "[i] You can compile the APK instantly using:" -ForegroundColor Yellow
    Write-Host "    1. Push to GitHub -> Actions tab -> Auto builds APK artifact" -ForegroundColor Cyan
    Write-Host "    2. Open 'android-project' folder in Android Studio and click Build APK" -ForegroundColor Cyan
}
