#!/usr/bin/env python3
"""Haber kaynaklarını (AA, NTV, BBC Türkçe) okuyup haberler.json dosyasına yazar.

TV tarayıcıları haber sitelerinden doğrudan veri çekemediği için (CORS),
bu betik GitHub Actions'ta 15 dakikada bir çalışır ve sonucu sitenin yanına koyar.
"""
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime
from html import unescape

KAYNAKLAR = [
    ("AA", "https://www.aa.com.tr/tr/rss/default?cat=guncel"),
    ("NTV", "https://www.ntv.com.tr/turkiye.rss"),
    ("BBC", "https://feeds.bbci.co.uk/turkce/rss.xml"),
]
ATOM = "{http://www.w3.org/2005/Atom}"
MEDIA = "{http://search.yahoo.com/mrss/}"


def indir(url):
    istek = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (OnurTV haber okuyucu)"})
    with urllib.request.urlopen(istek, timeout=20) as cevap:
        return cevap.read()


def temizle(metin):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", metin or ""))).strip()


def zaman_ms(metin):
    if not metin:
        return 0
    try:
        return int(parsedate_to_datetime(metin).timestamp() * 1000)
    except Exception:
        pass
    try:
        return int(datetime.fromisoformat(metin.replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        return 0


def metin(el, ad):
    bulunan = el.find(ad)
    return (bulunan.text or "").strip() if bulunan is not None and bulunan.text else ""


def resim_bul(el):
    img = el.find("image")
    if img is not None and (img.text or "").strip():
        return img.text.strip()
    for ad in (MEDIA + "thumbnail", MEDIA + "content", "enclosure"):
        m = el.find(ad)
        if m is not None and m.get("url"):
            return m.get("url")
    icerik = metin(el, ATOM + "content") or metin(el, "description")
    bulunan = re.search(r'<img[^>]+src="([^"]+)"', icerik or "")
    # NTV "format=webp" ile webp verir, "format=jpg"yi ise reddeder: biçim parametresi atılınca orijinal biçim gelir
    return re.sub(r"&?format=webp", "", bulunan.group(1)) if bulunan else ""


def oku(kaynak, veri):
    kok = ET.fromstring(veri)
    ogeler = kok.findall(".//item") or kok.findall(ATOM + "entry")
    sonuc = []
    for el in ogeler[:12]:
        baslik = metin(el, "title") or metin(el, ATOM + "title")
        ozet = metin(el, "description") or metin(el, ATOM + "summary")
        tarih = metin(el, "pubDate") or metin(el, ATOM + "published") or metin(el, ATOM + "updated")
        sonuc.append({
            "kaynak": kaynak,
            "baslik": temizle(baslik),
            "ozet": temizle(ozet)[:300],
            "resim": resim_bul(el),
            "zaman": zaman_ms(tarih),
        })
    return sonuc


def main():
    haberler = []
    for kaynak, url in KAYNAKLAR:
        try:
            haberler += oku(kaynak, indir(url))
        except Exception as hata:
            print(f"{kaynak} okunamadı: {hata}")
    haberler.sort(key=lambda h: h["zaman"], reverse=True)
    if not haberler:
        raise SystemExit("Hiç haber okunamadı, eski dosya korunuyor")
    with open("haberler.json", "w", encoding="utf-8") as f:
        json.dump({"guncelleme": int(time.time() * 1000), "haberler": haberler}, f, ensure_ascii=False)
    print(f"{len(haberler)} haber yazıldı")


if __name__ == "__main__":
    main()
