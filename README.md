# THE BERBER Randevu Sistemi

Bu klasor THE BERBER icin randevu ve musteri takip uygulamasidir.

## Ozellikler

- Musterilerin web sitesinden randevu almasi
- Hizmet, berber, gun ve saat secimi
- Doluluk kontrolu ve uygun saat hesaplama
- Musteri kayitlari
- PIN korumali yonetim paneli
- Randevu durumlari: bekliyor, onaylandi, tamamlandi, iptal, gelmedi
- SQLite veritabani ile ortak kayit tutma

## Calistirma

```bash
python3 app.py
```

Sonra:

- Musteri randevu sayfasi: `http://127.0.0.1:8010/`
- Yonetim paneli: `http://127.0.0.1:8010/admin`
- Demo yonetici PIN'i: `1234`

Yerel agdaki cihazlardan denemek icin:

```bash
HOST=0.0.0.0 PORT=8010 python3 app.py
```

## Gercek Yayina Alma

Baska insanlarin kendi telefonlarindan girebilmesi icin bu uygulamanin internete acik bir sunucuda calismasi gerekir. Domain, HTTPS, guclu yonetici sifresi, yedekleme ve SMS/e-posta bildirimleri canli kullanim icin eklenmelidir.

Ucretsiz yayin icin hazirlanan EU.org adresi:

```text
https://theberber.eu.org
```

Detaylar icin `DOMAIN.md` ve `EUORG_SETUP.md` dosyalarina bak.
