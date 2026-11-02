# GitHub'a yükleme

## Hazır kaynak paketi

`exports/BlexShot-source-v1.4.1.zip` kaynak kodu, logo/ikonları, testleri, belgeleri ve GitHub Actions yapılandırmasını içerir. ZIP'i açın ve **BlexShot klasörünün içeriğini** GitHub deposunun köküne yükleyin. ZIP dosyasını tek dosya olarak yüklemek kaynak deposu oluşturmaz. Gizli `.github`, `.gitignore` ve `.gitattributes` dosyalarını da ekleyin; bu dosyaları korumak için Git kullanmak uygundur.

Kaynak paketini yeniden oluşturmak için:

```powershell
.\.venv\Scripts\python.exe tools\prepare_github.py
```

Sanal ortam, `dist`, `build`, `artifacts`, yerel ayarlar ve geliştirme sohbet notları kaynak paketine girmez. Orijinal dosyalar yerelde korunur.

## Git ile ilk yükleme

GitHub'da boş bir **BlexShot** deposu oluşturun. Başlangıç README veya lisansını GitHub'da eklemeden devam edin. Aşağıdaki URL'de `KULLANICI_ADINIZ` bölümünü değiştirin:

```powershell
git init -b main
git add .
git status
git commit -m "Initial BlexShot 1.4.1 source"
git remote add origin https://github.com/KULLANICI_ADINIZ/BlexShot.git
git push -u origin main
```

Ana proje klasörü zaten bir Git deposuysa tekrar başlatmaya gerek yoktur. Commit kimliği istenirse kendi Git kullanıcı adınızı/e-posta adresinizi ayarlayın.

## Test ve EXE

`.github/workflows/windows.yml`, push ve pull request için Windows üzerinde testleri çalıştırır. `v1.4.1` gibi bir sürüm etiketi gönderildiğinde veya Actions → Windows → Run workflow ekranında **Build executable** seçildiğinde EXE de üretilir. Başarılı çalışmanın **Artifacts** bölümünden `BlexShot-windows-x64` indirilebilir. GitHub CI ilk kez yüklemeden sonra çalışacaktır; yerel testlerin geçmesi uzak workflow'un çalışmış olduğu anlamına gelmez.

## Kullanıcıya indirilebilir sürüm sunma

EXE dosyasını kaynak deposuna commit etmeyin. Yerelde doğrulanan `dist/BlexShot-v1.4.1.exe` dosyasını veya CI artifact'inden çıkan `BlexShot.exe` dosyasını GitHub **Releases → Draft a new release** ekranına ekleyin. Etiket olarak `v1.4.1` kullanabilirsiniz. Açıklamada Windows 10/11 x64, kurulum gerektirmemesi ve uygulamanın dijital imzasız olduğunu belirtin. Kaynak arşivi ile EXE ayrı dosyalardır.

## Lisans

Proje sahibinin lisans tercihi henüz belirlenmedi; hazırlık sırasında MIT/GPL gibi bir lisans atanmadı. Kaynak için istediğiniz lisansı seçtikten sonra köke `LICENSE` ekleyin ve README'deki lisans bölümünü güncelleyin. Logo kullanıcı tarafından sağlanmıştır; üçüncü taraf bileşenlerin bildirimleri `THIRD_PARTY_NOTICES.md` içinde bulunur.
