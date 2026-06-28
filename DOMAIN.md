# THE BERBER Ucretsiz Domain Plani

Secilen ucretsiz domain:

```text
https://theberber.eu.org
```

Render uzerindeki gecici/ucretsiz servis adresi:

```text
https://the-berber-randevu.onrender.com
```

## Neden bu secildi?

THE BERBER sadece statik bir tanitim sitesi degil; randevu olusturuyor, musteri kaydi tutuyor ve yonetim paneli var. Bu nedenle Netlify/Vercel gibi sadece statik ucretsiz adresler tek basina yeterli degil. Render ucretsiz web service, Python uygulamasini calistirabildigi icin bu proje icin daha uygun.

## Ek ucretsiz alan adi secenekleri

1. DuckDNS
   - Onerilen adres: `theberber.duckdns.org`
   - Hizli kurulur.
   - Daha cok ev/ofis bilgisayarina veya dinamik IP'ye yonlendirme icin uygundur.

2. EU.org
   - Onerilen adres: `theberber.eu.org`
   - Ucretsizdir ama manuel onay sureci olabilir.
   - Daha temiz bir alan adi gibi durur.

3. Render subdomain
   - Gecici adres: `the-berber-randevu.onrender.com`
   - EU.org onaylanana kadar kullanilabilir.

## Render'a yukleme adimlari

1. Projeyi GitHub'a yukle.
2. Render hesabina gir.
3. New > Web Service sec.
4. GitHub reposunu bagla.
5. Root directory olarak bu klasoru sec: `outputs/the-berber-app`
6. Render `render.yaml` dosyasini okuyarak servisi olusturur.
7. `THE_BERBER_ADMIN_PIN` icin guclu bir PIN gir.
8. Deploy bittiginde once Render adresi acilir:

```text
https://the-berber-randevu.onrender.com
```

9. EU.org + Cloudflare + Render baglama detaylari icin `EUORG_SETUP.md` dosyasini takip et.

## Onemli not

Render'in ucretsiz web servisinde yerel SQLite dosyasi kalici depolama icin ideal degildir. Canli kullanimda randevularin kaybolmamasi icin kalici veritabani gerekir. Ucretsiz demo icin yeterli; gercek salon kullanimi icin Postgres veya baska kalici veritabani eklenmelidir.
