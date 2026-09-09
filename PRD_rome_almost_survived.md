# PRD — "Why Rome ALMOST Survived: The 3 Moments That Nearly Saved the Empire"

## 1. Konsep
Video sejarah YouTube. Angle counterfactual **berbasis fakta** (bukan fantasi Roma-futuristik).
Premis: kejatuhan Roma Barat (476 M) **tidak tak-terhindarkan** — ada beberapa momen nyata
di mana kekaisaran hampir pulih, dipimpin jenderal/kaisar kompeten, dan gagal karena
sabotase internal (bukan kekuatan barbar). Setiap segmen: apa yang terjadi → seberapa dekat
Roma menang → apa yang menggagalkannya → "what if" singkat.

Kenapa angle ini: topik "What If Rome Never Fell" sangat JENUH di YouTube
(AlternateHistoryHub, Unveiled, puluhan channel AI). Angle "hampir selamat" = kredibel,
semi-faktual, footage stock realistis tersedia (reruntuhan/patung/koin/peta), tak butuh
visual AI Roma-futuristik yang mahal/buntu.

## 2. Target
- Durasi: 8-11 menit (long-form) ATAU versi Shorts 60s (opsi `--shorts`)
- Tone: naratif, kredibel, sedikit dramatis; bukan meme
- Audiens: penggemar sejarah, alt-history, penonton AlternateHistoryHub/Kings & Generals

## 3. Judul (kandidat)
1. **"Rome Almost Survived — The 3 Moments That Nearly Saved the Empire"** (utama)
2. "Why Rome DIDN'T Have to Fall — The Men Who Nearly Saved It"
3. "Rome's Last Chances: How the Western Empire Almost Recovered"

## 4. Fakta jangkar (terverifikasi — grounding naskah)
### Momen 1 — Stilicho (395-408 M)
- Jenderal separuh-Vandal, wali Kaisar Honorius. "The last great defender of the West".
- Kemenangan: Pollentia (402) & Verona (402) lawan Alaric; hancurkan invasi Radagaisus (406).
- Nyaris menstabilkan Barat. **Digagalkan:** intrik istana Honorius → ditangkap & dieksekusi 408.
- Akibat langsung: 2 tahun kemudian (410) Alaric menjarah Roma — pertama dalam 800 tahun.
- "What if": tanpa eksekusi Stilicho, Alaric mungkin tak pernah sampai ke gerbang Roma.

### Momen 2 — Aetius (433-454 M)
- "Last of the Romans". Arsitek koalisi yang kalahkan Attila di **Catalaunian Plains (451)**.
- Menjaga Gaul tetap Romawi lewat aliansi federate. **Digagalkan:** dibunuh langsung oleh
  tangan Kaisar Valentinian III sendiri (454) karena cemburu/curiga.
- Komentar kontemporer: "Kau memotong tangan kananmu dengan tangan kirimu."

### Momen 3 — Majorian (457-461 M)
- Kaisar Barat terakhir yang benar-benar cakap. Dalam 3 tahun: pukul mundur Vandal dari Italia,
  kalahkan Visigoth di Arelate, rebut kembali Hispania & Sisilia, reduksi Goth ke status federate,
  reformasi anti-korupsi (Novellae Maioriani — 12 UU masih terlestari).
- 460: siapkan armada besar untuk rebut Afrika dari Vandal (kunci pajak gandum).
- **Digagalkan:** pengkhianat disuap Vandal → armada dihancurkan di Cartagena SEBELUM berlayar.
  461: jenderalnya sendiri Ricimer memenggalnya. Semua penerus = boneka sampai 476.
- Procopius: Majorian "melampaui setiap kaisar Romawi dalam segala kebajikan".
- "What if": jika armada Afrika berhasil → pendapatan pulih → Roma Barat mungkin bertahan.

### Benang merah (kesimpulan video)
Roma Barat tidak jatuh karena barbar terlalu kuat — tapi karena **setiap kali seorang
penyelamat kompeten muncul, elite Romawi sendiri membunuhnya**. Pola bunuh-diri politik,
bukan takdir.

## 5. Outline naskah (long-form)
0:00 Hook — "476 bukan akhir yang tak terhindarkan. Tiga kali Roma nyaris selamat..."
0:40 Setup — kondisi Barat abad ke-5 (peta, tekanan barbar)
1:30 Momen 1: Stilicho — kemenangan → eksekusi → penjarahan 410
4:00 Momen 2: Aetius — Attila dikalahkan → dibunuh kaisarnya sendiri
6:15 Momen 3: Majorian — kebangkitan → armada dikhianati → dipenggal
9:00 Sintesis — pola: Roma bunuh penyelamatnya sendiri
9:45 Counterfactual singkat + CTA

## 6. Produksi (pipeline ytgen)
- `ytgen generate --topic "Why Rome almost survived: the 3 moments that nearly saved the empire"`
- Visual: footage stock Pexels/Pixabay — reruntuhan Romawi, patung, koin, Colosseum, peta,
  legiun/reenactment, pantai Mediterania (armada). Keyword harus konkret (hindari "star death"-type).
- Musik: Jamendo instrumental, mood epik/cinematic (mood tag: `cinematic` / `epic` / `ambient`).
- Naskah di-grounding pada fakta jangkar di atas (research.json + prompt).
- Caption PNG overlay, thumbnail auto.

## 7. Risiko / catatan
- **Akurasi**: naskah LLM bisa halusinasi tanggal/nama. Fakta jangkar di atas WAJIB jadi acuan;
  verifikasi tanggal (402 Pollentia, 408 Stilicho, 451 Catalaunian, 454 Aetius, 461 Majorian).
- Footage "armada Romawi" langka di stock → pakai kapal kuno/laut Mediterania sebagai proxy.
- Kompetisi tinggi → keunggulan = akurasi + angle "hampir selamat" yang jarang digarap.

## 8. Status
PRD selesai. Menunggu keputusan user: long-form atau Shorts, lalu jalankan pipeline.
