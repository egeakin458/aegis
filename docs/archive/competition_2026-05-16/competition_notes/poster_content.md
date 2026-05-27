# Aegis — Poster İçeriği (GBYF, 16 Mayıs 2026)

**Proje Sahibi:** Ege Akın · İzmir Ekonomi Üniversitesi, Bilgisayar Mühendisliği · Bitirme Projesi
**Yarışma:** GBYF (Genç Beyinler Yeni Fikirler), 16.05.2026

---

## 1. Proje Özeti (Abstract — ~120 kelime)

Aegis, **teknik bilgisi olmayan bir kullanıcının doğal dilde tarif ettiği yazılım fikrini, dört uzman yapay zekâ ajanının (Gereksinim Analisti, Çözüm Mimarı, Geliştirici, Kalite Güvence) yapılandırılmış JSON sözleşmeleri ve geri besleme döngüleri üzerinden çalıştırarak otomatik olarak tam yığın (full‑stack) bir web uygulamasına dönüştüren** bir çoklu‑ajan orkestrasyon sistemidir. Sistem; bir devlet makinesi (state machine), tipli iletişim sözleşmeleri (Pydantic / Zod), gerçek bir derleme (build) doğrulama aşaması ve canlı SSE akışı üzerinden çalışır. Çıktı; çalışır durumda bir Next.js 14 + SQLite projesidir. Aegis, "yapay zekâ destekli yazılım üretimini bireysel bir kod tamamlayıcısı olmaktan çıkarıp, denetlenebilir bir **sanal yazılım şirketi** disiplinine taşıma" iddiasındadır [1,2,3,4].

---

## 2. Problem ve Motivasyon (~110 kelime)

KOBİ'ler ve girişimciler için ısmarlama yazılım hâlâ pahalı, yavaş ve teknik aracı gerektiriyor. AB genelinde işletmelerin yaklaşık **%55'i BİT uzmanı bulmakta zorlanıyor**; Avrupa'nın 2030 hedefi 20 milyon uzmana karşın mevcut arz ~9 milyon civarında [9]. Türkiye'de BİT sektörünün büyüklüğü **1,2 trilyon TL'ye** ulaşmış olsa da KOBİ tarafında özel yazılım maliyeti hâlâ engelleyici [10,11]. Mevcut LLM tabanlı kod üreticileri ise (Copilot, tek‑istem üreticiler) bir **geliştiriciye yardım etmek** için tasarlanmıştır; gereksinim çıkarımı, mimari tutarlılığı ve kalite kontrolünü uçtan uca üstlenmezler [5,12,13]. Aegis, bu uçtan‑uca boşluğu denetlenebilir bir biçimde dolduruyor.

---

## 3. Amaç ve Hedefler (~80 kelime)

- **Erişilebilirlik:** Kod yazmayı bilmeyen bir kullanıcının ≤5 dakikada çalışır bir uygulama elde etmesi.
- **Denetlenebilirlik:** Her ajan kararının tipli JSON sözleşmesi, SQLite olay günlüğü ve SSE akışıyla **iz sürülebilir** olması.
- **Kalite kapısı:** Üretilen kodun gerçek bir `next build` doğrulamasından ve QA inceleme döngüsünden geçmesi.
- **Bilimsel katkı:** Çerçeve‑bağımsız (LangChain/CrewAI **kullanmadan**), kendi orkestrasyon disiplinini ortaya koyan açık bir referans mimari.

---

## 4. Teknik Yaklaşım ve Sistem Mimarisi (~160 kelime)

Aegis üç katmanlı bir mimaridir:

1. **Pipeline Engine** — `PipelineRunner` adlı asenkron bir **devlet makinesi**: `INTAKE → REQUIREMENTS → [CLARIFICATION ↔ REQUIREMENTS] → DESIGN → DEVELOPMENT → BUILD_CHECK → REVIEW → COMPLETE`. Her ajan `BaseAgent`'tan türer; LLM çağrısı, JSON ayrıştırma, Pydantic doğrulaması ve tek seferlik retry merkezîdir.
2. **Lifecycle Manager** — Tekil `RunnerManager`; HTTP ile ajan motoru arasında köprü, SQLite kalıcılığı, SSE kuyruğu ve `asyncio` görev yönetimi.
3. **API & Persistence** — FastAPI + `aiosqlite`; üretilen kod `outputs/{run_id}/` altına ve `manifest.json`'a yazılır.

**Ajanlar arası sözleşmeler** doğal dil değil, **Pydantic v2 şemalarıdır** (`CustomerConfigV2` DDC v1, `TechnicalDesign`, `CodeOutput`, `CodePatch`, `QAReview`). Bu tasarım, MetaGPT'nin "SOP olarak prompt zinciri" [1] ve ChatDev'in "iletişimsel halüsinasyon azaltma" [2] yaklaşımlarıyla aynı aileden olmakla birlikte; **kendi orkestrasyonunu** zorunlu kılar — LangChain, CrewAI veya AutoGen [3] gibi çerçeveler tezin entelektüel katkısının yerini almaması için yasaklıdır.

> Şekil 1: Pipeline veri akışı (poster diyagramı için: docs/uml/AegisComponentDiagram.{png,svg}).

---

## 5. Bilimsel Yöntem Tasarımı (~140 kelime)

Aegis, **deneysel olarak ölçülebilir** bir sistem olarak tasarlanmıştır:

- **Birim test kapsaması:** 288/288 backend, 72/72 frontend testi geçer durumdadır.
- **Benchmark protokolü:** `evaluation/run_benchmark.py`; standart DDC tanımlı senaryolar (todo, e‑ticaret, guestbook). Sonuç metrikleri: (a) **özellik kapsaması** (RA'nın çıkardığı use‑case'lerin QA tarafından "çalışır" olarak işaretlenme oranı), (b) **test başarısı**, (c) **duvar saati (wall‑time)**, (d) **token tüketimi**, (e) **revizyon döngüsü sayısı**.
- **Mevcut sonuçlar:** `benchmark_02_todo_ddc` üzerinde **100% özellik/test skoru, 231,8 s duvar saati, 0 revizyon** (run `ab4f5a1e`, 2026‑05‑10).
- **Referans aileler:** Değerlendirme tasarımı SWE‑bench [6] ve `Agent4SE` taksonomisinden [4] esinlenir; ancak Aegis "gerçek GitHub issue çözmek" yerine "sıfırdan tam uygulama üretmek" görevini ölçer — bu da güncel taksonomide "**end‑to‑end software development**" alt‑görevine karşılık gelir [4,5].

---

## 6. Yenilikçi Yönler (~140 kelime)

1. **Çerçeve‑bağımsız orkestrasyon:** MetaGPT [1] ve ChatDev [2] kendi çerçeveleridir; AutoGen [3] genel‑amaçlıdır. Aegis hiçbir orkestrasyon kütüphanesi kullanmaz — devlet makinesi, ajan tabanı ve şema sözleşmeleri **sıfırdan yazılmıştır**; bu da tezin doğrudan katkısıdır.
2. **Pause‑and‑Resume Clarification:** Belirsiz girdilerde pipeline `CLARIFICATION` durumuna **gerçekten durur**, kullanıcı yanıtıyla aynı oturumda devam eder — sürekli SSE bağlantısı kopmadan.
3. **Gerçek build doğrulaması:** Pre‑seeded sandbox üzerinde gerçek `next build`; ~30 sn'de çalışır. Halüsinasyon kodu **derleme aşamasında** yakalanır.
4. **Patch‑modu Geliştirici:** Revizyon turlarında Developer ajanı tam dosya değil `CodePatch` (diff) üretir — token tasarrufu ve odaklı düzeltme.
5. **DDC v1 — 4D müşteri modeli:** Actor / DomainEntity / UseCase / BusinessRule + Relationship; referans bütünlüğü `model_validator` ile zorlanır. Bu, ajanlar arası "fikir kayması"nı sözleşme düzeyinde engeller.

---

## 7. Sektöre ve Ülke Ekonomisine Katkı (~150 kelime)

**Pazar bağlamı:** Gartner, kurumsal uygulamaların **2025'te %70'inin** low‑code/no‑code teknolojileriyle üretileceğini öngörüyor [7]; küresel low‑code pazarı 2026'da **44,5 milyar $'a**, 2029'da 58,2 milyar $'a ulaşıyor [7]. McKinsey, üretken YZ ile yazılım görevlerinin **2 kata kadar** hızlandığını ölçtü [8]; GitHub Octoverse 2024, Copilot kullanımının üretkenliği **%55 artırdığını** raporladı [12].

**Yetenek açığı:** OECD'nin "Bridging Talent Shortages in Tech" raporu, gelişmiş ekonomilerde teknoloji uzmanı arz‑talep dengesizliğinin yapısal hâle geldiğini belgeliyor [14]; AB'de işletmelerin **~%55'i** BİT uzmanı bulmakta zorlanıyor [9]. Aegis tam da bu açığı, "uzmana erişimi olmayan KOBİ'lere yazılım üretim kapasitesi taşıyarak" hedef alır.

**Türkiye'ye etki:** TÜBİSAD'ın Mayıs 2025'te açıkladığı 2024 raporuna göre BİT sektörümüz **1 trilyon 203,5 milyar TL** hacme (yıllık %53 büyüme), BT yazılım ihracatı **%98 büyüyerek 103,8 milyar TL'ye** ulaştı [10]. Sektörün GSYH içindeki payı %2,77 — küresel BİT pazarındaki payımız ise hâlâ **%0,72** [10]. KOSGEB **KOBİ Dijital Dönüşüm Destek Programı** (20 milyon TL'ye varan destek) tam da bu kapasiteyi büyütmeyi hedefliyor [11]. Aegis, KOBİ'lerin ısmarlama yazılıma erişim maliyetini **fikirden ürüne ~5 dakikaya** indirerek bu dönüşümün **uygulama katmanı** olmaya adaydır.

---

## 8. Uygulanabilirlik (~110 kelime)

- **Demo‑hazır:** Yerel olarak `uvicorn` + `npm run dev`; üretilen her uygulama **kendi başına çalışır** Next.js 14 + SQLite projesidir. Tek `npm install && npm run dev` ile ayağa kalkar.
- **Bulut dağıtımı:** Railway (backend) + Vercel (frontend) için hazırdır; halen yerel demo modunda.
- **Model temeli:** Aegis, ana ajanlarda **Claude Sonnet 4.6** (SWE‑bench Verified: **%79,6**), yardımcı görevlerde Haiku 4.5 kullanır. Karşılaştırma: Sonnet 4.5 yüksek‑hesapta %82,0, standart konfigürasyonda %77,2 — yani sınıfının önünde bir agentic kodlama temeli [13].
- **Maliyet profili:** Bir todo uygulaması ≤232 sn ve birkaç sent ($) maliyetle üretiliyor.
- **Genişletilebilirlik:** Yeni ajan eklemek = `BaseAgent` türetmek + şema yazmak + state machine'e handler kaydı (~50 satır). Stack genişletmek = `_ALLOWED_DEPS` listesini ve sandbox'ı güncellemek.
- **Sınırlar:** Tek müşteri / tek koşum hedefli; oturum yönetimi ve ölçeklenme bilinçli olarak kapsam dışı (tez sınırı).

---

## 9. Mevcut Sonuçlar (~70 kelime)

- 288/288 birim test (backend), 72/72 (frontend) — yeşil.
- `benchmark_02_todo_ddc`: **100% özellik/test, 231,8 s, 0 revizyon** (`ab4f5a1e`, 2026‑05‑10).
- `benchmark_03_guestbook_ddc`: tam uygulama, ekran görüntüleri `docs/guestbook_screenshots/`.
- Real‑time UX: SSE üzerinden 4 ajanın çalışması, dosya yazımları, build doğrulaması ve QA bulguları **canlı** izleniyor.

---

## 10. İlham ve Faydalanılan Kaynaklar

Aegis'in akademik olarak konumlandığı aile: **LLM‑tabanlı çoklu‑ajan yazılım mühendisliği** [4,5]; doğrudan ilham aldığı (ve **kütüphane olarak kullanmadığı**) öncüller MetaGPT [1], ChatDev [2] ve AutoGen [3]. Ölçüm felsefesi SWE‑bench [6] ile aynı ailededir. Endüstriyel bağlam Gartner low‑code öngörüleri [7], McKinsey üretkenlik çalışmaları [8] ve GitHub Octoverse 2024 [12] ile çerçevelenir. Yerel ekonomi argümanı TÜBİSAD [10] ve KOSGEB [11] verileri üzerine kurulur.

---

## Referanslar

1. Hong, S. et al. **MetaGPT: Meta Programming for A Multi‑Agent Collaborative Framework.** ICLR 2024 (Oral). arXiv:2308.00352. https://arxiv.org/abs/2308.00352
2. Qian, C. et al. **ChatDev: Communicative Agents for Software Development.** ACL 2024 (Long). https://aclanthology.org/2024.acl-long.810/
3. Wu, Q. et al. **AutoGen: Enabling Next‑Gen LLM Applications via Multi‑Agent Conversation.** COLM 2024. arXiv:2308.08155. https://arxiv.org/abs/2308.08155
4. Hou, X. et al. **LLM‑Based Multi‑Agent Systems for Software Engineering: Literature Review, Vision and the Road Ahead.** arXiv:2404.04834 (2024–2025). https://arxiv.org/abs/2404.04834
5. He, J. et al. **From LLMs to LLM‑based Agents for Software Engineering: A Survey of Current, Challenges and Future.** arXiv:2408.02479 (2024). https://arxiv.org/abs/2408.02479
6. Jimenez, C. E. et al. **SWE‑bench: Can Language Models Resolve Real‑World GitHub Issues?** ICLR 2024. arXiv:2310.06770. https://arxiv.org/abs/2310.06770
7. Gartner. **Forecast Analysis: Low‑Code Development Technologies, Worldwide (2026 görünüm: 44,5 mlr $; 2029: 58,2 mlr $; 2025'te yeni kurumsal uygulamaların %70'i LCNC).** https://www.gartner.com/en/documents/7146430 ; özet: https://kissflow.com/low-code/gartner-forecasts-on-low-code-development-market/
8. McKinsey & Company. **Unleashing Developer Productivity with Generative AI** — üretken YZ ile yazılım görevlerinde **2 kata kadar** hızlanma. https://www.mckinsey.com/capabilities/tech-and-ai/our-insights/unleashing-developer-productivity-with-generative-ai
9. European Commission. **Digital Skills and Jobs** — AB'de işletmelerin ~%55'i BİT uzmanı bulmakta zorlanıyor; 2030 için 20 milyon uzman hedefi. https://digital-strategy.ec.europa.eu/en/policies/digital-skills-and-jobs
10. TÜBİSAD. **Türkiye BİT Sektörü 2024 Raporu** (lansman: 29 Mayıs 2025, İTÜ) — 1 trilyon 203,5 milyar TL pazar (yıllık %53 ↑); BT yazılım ihracatı %98 ↑ → 103,8 milyar TL; küresel BİT payı %0,72; GSYH içindeki pay %2,77. Lansman duyurusu: https://www.log.com.tr/tubisad-turkiye-bilgi-ve-iletisim-teknolojileri-sektorunun-buyuklugu-12-trilyona-ulasti · Resmî rapor arşivi: https://www.tubisad.org.tr/tr/bilgi-bankasi/sunumlar-liste/TUBISAD-Raporlar/40/0/0
11. KOSGEB. **KOBİ Dijital Dönüşüm Destek Programı** — yazılım, mobil uygulama, veri analizi, siber güvenlik için 20 milyon TL'ye varan destek. https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9144/kobi-dijital-donusum-destek-programi
12. GitHub. **Octoverse 2024** — Copilot ile üretkenlik %55 artışı; Fortune 100'ün ~%90'ında dağıtık. https://github.blog/news-insights/octoverse/octoverse-2024/
13. Anthropic. **Claude Sonnet 4.6** (lansman, Ekim 2025) — SWE‑bench Verified **%79,6** (10‑deneme ortalama, max effort, 3× thinking budget); önceki sürüm Sonnet 4.5 standart %77,2 / yüksek‑hesapta %82,0. https://www.anthropic.com/news/claude-sonnet-4-6 · Sistem kartı: https://www.anthropic.com/claude-sonnet-4-6-system-card · Sonnet 4.5 referansı: https://www.anthropic.com/news/claude-sonnet-4-5
14. OECD. **Bridging Talent Shortages in Tech.** https://www.oecd.org/en/publications/bridging-talent-shortages-in-tech_f35da44f-en.html
15. Aegis kaynak kodu: `github.com/egeakin458/aegis` (varsayılan branch `main`). **AKSİYON GEREKLİ:** Repo şu an private; **sergi sabahı public'e alınmalı** (`gh repo edit egeakin458/aegis --visibility public --accept-visibility-change-consequences`).

---

## Poster Yerleşim Önerisi (görsel akış)

**Hazır görsel varlıklar (poster baskısı için, hepsi UML 2.5 — PNG + SVG):**
- **Şekil 1 — Component Diagram (3 katmanlı mimari):** `docs/uml/AegisComponentDiagram.{png,svg}` — 2001×779, ana mimari görseli için önerilen.
- **Şekil 2 — Sequence Diagram (uçtan uca akış):** `docs/uml/AegisSequenceDiagram.{png,svg}` — 1520×1889, dikey kolon olarak posterde kullanılabilir.
- **Şekil 3 — State Machine Diagram (PipelineRunner):** `docs/uml/AegisStateMachine.{png,svg}` — 1619×990, "Bilimsel Yöntem Tasarımı" bölümünün yanına önerilir.
- **Şekil 4 — Üretilmiş uygulama ekran görüntüleri:** `docs/guestbook_screenshots/` (pipeline'ın her fazını gösterir).
- **PlantUML kaynak dosyaları** (post-hoc düzenleme için): `docs/uml/01_component_diagram.puml`, `02_sequence_diagram.puml`, `03_state_machine.puml`. Yeniden render: `java -jar docs/uml/plantuml.jar -tpng -tsvg docs/uml/*.puml`.
- **Tablo 1 — Benchmark sonuçları** (bar/grafik üretmek yerine doğrudan tablo önerilir, baskıda daha güvenli):

| Benchmark | Özellik skoru | Test skoru | Duvar saati | Revizyon | Run ID |
|---|---|---|---|---|---|
| `benchmark_02_todo_ddc` | 100% | 100% | 231,8 s | 0 | `ab4f5a1e` (2026‑05‑10) |
| `benchmark_03_guestbook_ddc` | tam uygulama üretildi | — | — | — | `docs/guestbook_screenshots/` |

```
┌───────────────────────────────────────────────────────────┐
│  AEGIS — Sanal Yazılım Şirketi: 4 YZ Ajanı, Tam Stack    │
│  Ege Akın  ·  IUE Bilgisayar Müh.  ·  GBYF 16.05.2026    │
├───────────────────┬───────────────────────────────────────┤
│ 1. ÖZET           │   ŞEKIL 1: Sistem Mimarisi            │
│ 2. PROBLEM        │   (docs/uml/AegisComponentDiagram.{png,svg})      │
│ 3. AMAÇ           │                                       │
├───────────────────┼───────────────────────────────────────┤
│ 4. MİMARİ         │   ŞEKIL 2: Üretilmiş Uygulama         │
│ 5. BİLİMSEL YÖNT. │   (docs/guestbook_screenshots/*)      │
│ 6. YENİLİKLER     │                                       │
├───────────────────┼───────────────────────────────────────┤
│ 7. EKONOMİK ETKİ  │   TABLO 1: Benchmark Sonuçları        │
│ 8. UYGULANABİLİR. │   (yukarıdaki tablodan)               │
│ 9. SONUÇLAR       │                                       │
├───────────────────┴───────────────────────────────────────┤
│ KAYNAKLAR (1–15)        QR: github.com/egeakin458/aegis  │
└───────────────────────────────────────────────────────────┘
```
