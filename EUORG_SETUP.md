# theberber.eu.org Baglama Plani

Hedef ucretsiz domain:

```text
theberber.eu.org
```

Canli site adresi:

```text
https://theberber.eu.org
```

## Durum

Genel DNS kontrolunde `theberber.eu.org` aktif bir kayit dondurmedi. Bu, alan adinin kayit icin uygun olabilecegini gosterir; kesin uygunluk ve onay EU.org panelinde belli olur.

## Gerekli hesaplar

Bu islemler hesap ve onay gerektirdigi icin otomatik tamamlanamaz:

- EU.org hesabi
- Ucretsiz DNS hesabi, onerilen: Cloudflare Free
- Render hesabi

## 1. Cloudflare DNS hazirla

Cloudflare'da yeni site/zone olarak sunu ekle:

```text
theberber.eu.org
```

Cloudflare sana iki nameserver verir. Ornek format:

```text
xxxx.ns.cloudflare.com
yyyy.ns.cloudflare.com
```

Bu iki nameserver'i EU.org kaydinda kullanacaksin.

## 2. EU.org kaydi

EU.org panelinde yeni domain istegi olustur:

```text
Complete domain name: theberber.eu.org
```

Nameserver alanlarina Cloudflare'in verdigi iki nameserver'i yaz.

EU.org kaydi manuel onaylanabilir; bu bazen hemen olmaz.

## 3. Render custom domain

Render'da THE BERBER servisinde custom domain olarak ekle:

```text
theberber.eu.org
www.theberber.eu.org
```

Render servisi su adla hazirlandi:

```text
the-berber-randevu
```

Render'in ucretsiz varsayilan adresi:

```text
https://the-berber-randevu.onrender.com
```

## 4. Cloudflare DNS kayitlari

EU.org onayindan sonra Cloudflare DNS'e su kayitlari gir:

```text
Type: A
Name: @
Value: 216.24.57.1
Proxy: DNS only
```

```text
Type: CNAME
Name: www
Value: the-berber-randevu.onrender.com
Proxy: DNS only
```

Render farkli bir hedef verirse Render'in gosterdigi degeri kullan.

## 5. Son kontrol

Asagidaki adresler acilmali:

```text
https://theberber.eu.org
https://www.theberber.eu.org
```

Yonetim paneli:

```text
https://theberber.eu.org/admin
```
