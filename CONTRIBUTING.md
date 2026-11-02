# Geliştirme

Windows üzerinde 64 bit Python 3.12 veya üstünü kullanın. Teslim sürümü Python 3.14 ile doğrulandı.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe main.py
```

Tam sürümleri yeniden kurmak için Python 3.14 ile `requirements-lock.txt` kullanın. EXE üretmek ve bağımsız açılışını doğrulamak için `build.bat` çalıştırın.

## Hata bildirme

Windows sürümünü, BlexShot sürümünü, monitör sayısı ve ölçeklerini, sorunu tekrar oluşturan adımları ve beklenen sonucu yazın. Gerekirse kişisel içerikleri gizleyerek ekran görüntüsü ekleyin. Kısayol sorunu için atanan tuşu ve görünen hata mesajını belirtin.

## Değişiklik gönderme

Değişikliği ayrı bir dalda hazırlayın. İlgili testleri çalıştırın; arayüz değişikliğinde ekran görüntüsü ekleyin. Yakalama akışında ana editörün kendiliğinden açılmaması ve fiziksel piksel koordinatlarının korunması gerekir. Masaüstü entegrasyon yardımcıları panoya test görüntüsü yazabilir ve global tuş kaydı yapabilir; bu testleri yerel Windows masaüstünde çalıştırın.

Sanal ortamı, EXE dosyalarını, test çıktısını ve yerel tercihleri kaynak değişikliğine eklemeyin. Proje lisansı henüz seçilmediği için katkı koşulları proje sahibiyle netleştirilmelidir.
