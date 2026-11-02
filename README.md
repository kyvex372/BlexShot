<p align="center">
  <img src="resources/app.png" width="88" alt="BlexShot logosu">
</p>

<h1 align="center">BlexShot</h1>
<p align="center"><strong>Yakala. Düzenle. Paylaş.</strong><br>Windows için kompakt ekran yakalama ve anında düzenleme aracı.</p>

BlexShot, ekranın istediğiniz bölümünü yakalayıp doğrudan üzerinde çalışmanızı sağlar. Ok ekleyin, not yazın, hassas bölgeleri gizleyin ve sonucu tek hareketle kopyalayın veya kaydedin. Görüntüler yerel olarak işlenir; bir sunucuya gönderilmez.

![BlexShot kompakt yönetim ekranı](docs/images/management.png)

## Özellikler

- **Üç yakalama modu:** seçili alan, tüm monitörler veya aktif pencere.
- **Ekran üzerinde düzenleme:** ayrı bir editör penceresi açılmadan kalem, ok, şekil, metin ve numaralı işaret ekleme.
- **Gizleme araçları:** blur, pikselleştirme ve opak sansür bölgeleri.
- **Kompakt kontrol merkezi:** üst sekmeler, açık/koyu tema ve atanabilir global kısayollar.
- **Kalite kontrolü:** PNG, JPEG ve WebP; kayıplı biçimlerde ayarlanabilir kayıt kalitesi.
- **Hızlı paylaşım:** panoya kopyalama, arka planda dışa aktarma ve sistem tepsisinden kullanım.

<details>
<summary>Ekran üstü araç paneli</summary>

![Kompakt BlexShot araç paneli](docs/images/capture-tools.png)

Araç seçenekleri **Ayarlar** ile açılır. Metin aracı, canlı yazı alanını otomatik gösterir.

</details>

[Windows sürümünü indir](https://github.com/kyvex372/BlexShot/releases/latest) · [Hata bildir](https://github.com/kyvex372/BlexShot/issues)

## Kullanım

1. BlexShot'u açın; tepsi simgesine sol tıklayın veya `Print Screen` tuşuna basın.
2. Yakalamak istediğiniz alanı sürükleyerek seçin.
3. Alanın üzerinde çizin, metin ekleyin veya gizlemek istediğiniz bölgeleri işaretleyin.
4. `Ctrl+C` ile kopyalayın veya `Ctrl+S` ile kaydedin. `Esc` ile işlemi iptal edin.

Tepsi simgesine sağ tıklayarak ayarlara, yakalama modlarına ve isteğe bağlı dosya editörüne ulaşabilirsiniz. Varsayılan kısayollar: alan için `Print Screen`, tüm ekranlar için `Ctrl+Print Screen`, aktif pencere için `Alt+Print Screen`.

Hazır EXE Windows 10/11 **x64** içindir ve Python kurulumu gerektirmez. Uygulama dijital olarak imzalı değildir.

## Kaynaktan çalıştırma

Windows ve 64 bit Python **3.12+** gerekir. Sürüm 1.4.1, Python 3.14 ile doğrulandı.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

İlk kurulumdan sonra `run.bat` ile konsol penceresiz başlatabilirsiniz. Tam bağımlılık sürümleri `requirements-lock.txt` içinde bulunur.

## EXE oluşturma

```powershell
.\build.bat
```

Bu komut bağımlılıkları kurar, ikonları üretir, testleri çalıştırır, `dist/BlexShot.exe` oluşturur ve bağımsız açılışını doğrular. GitHub Actions yapılandırması da Windows testleri ve isteğe bağlı EXE artifact'i için hazırdır.

## Geliştirme ve doğrulama

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Sürüm 1.4.1 için **46 otomatik test**, Windows üzerinde kısayol kayıt/çakışma akışları ve iki monitörde ekran üstü çizim, kopyalama ve kaydetme kontrolleri geçti. Farklı ölçeklerin birlikte kullanıldığı monitör düzenleri fiziksel olarak doğrulanmadı.

- [Ayrıntılı kullanım, ayarlar ve teknik sınırlar](docs/USAGE.md)
- [Katkı ve hata bildirme](CONTRIBUTING.md)
- [Sürüm notları](docs/RELEASES.md)
- [GitHub yükleme ve derleme rehberi](docs/GITHUB.md)

## Lisans

Proje için henüz açık kaynak lisansı seçilmemiştir. Üçüncü taraf bileşenlerin lisansları kendilerine aittir; [bildirimlere](THIRD_PARTY_NOTICES.md) bakın. BlexShot logosu proje sahibi tarafından sağlanmıştır.
