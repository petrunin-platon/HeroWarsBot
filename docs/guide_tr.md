# Hero Wars RPA Botu v1.0 Kapsamlı Kullanım Kılavuzu

Selam! Hero Wars otomasyon sistemine hoş geldin. 

Şunu hemen netleştirelim: Bu bot, ekrana rastgele tıklayan aptal bir program değil. O senin akıllı kişisel asistanın (RPA ajanı). Oyun ekranını "görebilir", titanlarının can durumunu analiz edebilir, istatistik toplayabilir ve Zindan temizliği sırasında anlık taktiksel kararlar alabilir.

Farm yapmayı zahmetsiz, güvenli ve maksimum kaynak getirecek hale getirmek için her şeyi adım adım nasıl kuracağını inceleyelim.



## Bölüm 1. Telefon ve Bilgisayarı Eşleştirme

Bot, oyunu özel bir ekran yansıtma programı (scrcpy) aracılığıyla yönetir. Botun kontrolü ele alabilmesi için telefonunu bir kereliğine yapılandırman gerekiyor.

* **"USB Hata Ayıklama"yı Aç:** Android telefonunda Ayarlar -> Geliştirici Seçenekleri bölümüne git ve "USB Hata Ayıklama" seçeneğini aktif et. Eğer "Geliştirici Seçenekleri" gizliyken, "Telefon Hakkında" kısmındaki "Derleme Numarası"na 7 kez üst üste tıkla.
* **Kabloyu Bağla:** Telefonunu kaliteli bir USB kablosuyla bilgisayara bağla. Telefonda "Bu bilgisayardan hata ayıklamaya izin verilsin mi?" sorusu belirecektir. "Her zaman izin ver" seçeneğini işaretle ve "Tamam"a bas.
* **Oyuna Gir:** Hero Wars'u aç, Zindan'a gir ve koridorda (bir sonraki kapının göründüğü yerde) bekle.
* **Botu Bağla:** Program arayüzümüzdeki "1. Telefonu Bağla" butonuna tıkla. Bilgisayar ekranında telefonunun ekranını gösteren bir pencere açılacaktır.

**➡ EN ÖNEMLİ KURAL:** Bot, oyunu tıpkı senin gibi kendi dijital gözleriyle "görür". Ekran yansıtma penceresi bilgisayarında her zaman görünür olmalıdır! Bu pencere simge durumuna küçültülmemeli, tarayıcıyla kapatılmamalı veya ekranın dışına taşınmamalıdır. Eğer pencerenin önü kapanırsa, bot durur ve ekranı tekrar görene kadar bekler.

**➡ Gece Farmı:** Eğer botu gece açık bırakmak istiyor ama telefon ekranının yıpranmasını istemiyorsan, Kontrol Paneli'ndeki "Ekranı KAPAT" butonunu kullan. Telefonunun ekranı kararır (siyah olur), ancak oyun arka planda çalışmaya devam eder ve bot her şeyi görmeye devam eder!



## Bölüm 2. Oturum Hedefleri (Kontrol Paneli)

Bota "Lonca barajına ulaşana kadar kasıl, sonra dinlenmeye geç" diyebilirsin. "Kurallar Sihirbazı" sekmesine git ve hedefini seç:

* Titanit Miktarına Göre (örneğin, 150'de dur).
* Oda Sayısına Göre (örneğin, tam 10 kapı geç).
* Katlara Göre (2 kat temizle).
* Süreye Göre (tam 30 dakika farm yap).

Limitleri belirledikten sonra Ana Sekmeye dön ve "2. Farmı Başlat" butonuna bas. Bot pencere boyutunu kendisi ayarlayacak, doğru kadroyu kuracak ve savaşa koşacaktır.



## Bölüm 3. Kurallar Sihirbazı (Bota Düşünmeyi Öğretme)

Zindanda 4 tip oda bulunur: Toprak, Su, Ateş ve Karışık. Botun sadece rastgele tıklamak yerine deneyimli bir oyuncu gibi kararlar alması için her bir elementin mantığını özel olarak yapılandırabilirsin.

**1. Varsayılan Kadro (Standart Takım)**

Bu, botun varsayılan olarak kullanacağı ana kadrondur. Başlangıçta tüm yuvalar boştur.

* İlgili elementin mavi butonuna tıkla (örneğin "Su").
* Açılan pencerede 3 ila 5 titan seç (genellikle tam bir beşli kurulur; örneğin Hyperion, Sigurd, Tethys, Nova, Mairi).
* Yeşil "Uygula" butonuna bas.

Eğer oyunda her şey planlandığı gibi gidiyorsa ve can durumları normalse, bot her zaman bu kadroyla oynayacaktır.

**2. Kural Tasarımcısı (Müdahaleler)**

Bazen işler kontrolden çıkabilir. İşte bu yüzden kurallara ihtiyacımız var (**"+ Koşul"** butonu). Bot her kapıdan önce durumu değerlendirir ve kadroyu değiştirerek kontrolü ele alabilir. Kuralın adını kendin belirlersin — bu isim mekanik olarak hiçbir şeyi etkilemez, sadece senin takip etmeni kolaylaştırır.

Koşullar üç tipe ayrılır:

* **Can Durumuna Göre (HP):** Örneğin tankın Sigurd sık sık çok hasar alıyor. Şöyle bir kural oluşturabilirsin: *"Eğer Sigurd'un HP'si %35'in altına düşerse, şifacılı kadroyu (Iyari) seç"*. En önemli kural: İyileştirme müdahalesini **kesinlikle o titanının iyileşebileceği element odasında oluşturmalısın!** (Sigurd için bu, Su odası veya Karışık odadır).

* **Enerjiye Göre:** "Hızlı" kadrolar için son derece kritiktir. Örneğin Angus'un Toprak odasındaki düşmanları tek bir ultiyle saniyeler içinde yok ediyor ve onların vurmasına izin vermiyor. Ancak bunun için savaşa enerjisi dolu girmesi gerekir. Şöyle bir kural oluştur: *"Eğer Angus'un Enerjisi %97'nin altındaysa - botu durdur"*. Bot Toprak odasına geldiğinde bir sinyal sesi verir ve durur; böylece Karışık odaya manuel girip Angus'a enerji biriktirebilirsin.

* **Düşmanlara Göre (Anti-Kadrolar):** Eğer düşman Araji'den nefret ediyorsan (takımını yakıp kavuruyorsa), şu kuralı ayarla: "Eğer düşmanlar arasında Araji varsa, özel anti-kadromu sahaya sür."

**3. Akıllı Seçenekler (Atlama ve Isınma)**

Kural Tasarımcısı'nda saçma ölümlerin önüne geçen özel onay kutuları bulunur:

* **Odaya Girişi Yasakla (Atla - Skip):** Diyelim ki Sigurd'un sadece %10 HP'si kaldı ve botun önünde Karışık oda var. Oraya girerse Sigurd kesin ölür. HP %20'nin altına düştüğünde "Skip" (Girişi Yasakla) kutusunu işaretlersin. Bot ağır yaralı Sigurd'u görür, Karışık odayı pas geçer ve onu iyileştirmek için bir Su odası aramaya koyulur.

* **Titanlar için Isınma Turu İste:** Yeni oyun gününün başlangıcı için benzersiz bir özellik! Sabahları tüm titanların HP'si %100'dür ancak enerjileri %0'dır. Onları doğrudan zorlu bir Karışık odaya sokarsan, ulti atamadan yere serilebilirler. "Isınma turu" kutucuğu bota şunu söyler: "Bu titan, karışık odalara girmeden önce mana biriktirmek için önce kendi elementinde en az bir kolay savaşa girmelidir."

**4. Öncelikler: Hangisi Daha Önemli?**

Sigurd'un HP'si azken ve aynı zamanda karşısında korkunç Araji duruyorsa bot ne yapmalı?
Bot, kurallar listeni gerçek bir insan gibi **kesinlikle yukarıdan aşağıya doğru** okur.

Gri renkli **"Aktif Kuralları Görüntüle/Sil"** butonuna bas. Orada botun mantığını göreceksin. Her şeyi şu şekilde gruplandırır:

1. **İlk olarak "Skip" kuralları** (canı az olan titanları savaşa sokmama).
2. **Ardından HP ve Enerjiye göre kurtarma kuralları**.
3. **Sonrasında anti-kadrolar (düşmana göre)**.
4. **En sonda ise** — eğer hiçbir tehdit yoksa — **Varsayılan Kadro**.

Bu pencerede kuralları oklarla (Yukarı/Aşağı) hareket ettirebilirsin. Listede üstte olan kurala bot her zaman öncelik verir. Sıralamayı değiştirdiysen, oradaki yeşil **"Değişiklikleri Kaydet"** butonuna basmayı unutma.

**5. ÖNEMLİ: Bot Hafızayı Nasıl Kaydeder?**

Botun arayüzü, sabit diskini sürekli yazma işlemleriyle yormamak ve ışık hızında çalışmak üzere tasarlanmıştır.

1. Kuralları ayarladıktan sonra, ana ekrandaki **mor "Profili Kaydet" butonuna** mutlaka bas.
2. "Farm" butonuna bastığında, bot tüm kuralları **bir kereliğine** okur ve geçici belleğe (RAM) yükler.
3. Eğer bot zaten farm yapıyorsa ve sen anlık olarak kuralları değiştirip kaydettiysen, bot bunları Görmez! Botun yeni ayarları algılaması için "Durdur" tuşuna basıp ardından "Farm"ı yeniden başlatman gerekir.

**➡ "Geri Yükle / Sıfırla" Butonu:** Ani bir elektrik kesintisi veya sistem hatası nedeniyle ayar dosyası bozulursa, farmı başlatmadan ÖNCE bu kırmızı butona basman yeterlidir. Bot otomatik olarak yedek kopyayı çekecek ve her şeyi düzeltecektir.

**6. Genel Angus Kontrolü**

**"Angus Ultisini Manuel Kontrol Et (Genel)"** anahtarı boşuna ana ekrana konmadı. Bot, Angus'u çoğu insandan daha iyi oynatır: Köklerin maksimum hasar vermesi için tam 1.8 saniye bekler ve ardından ultiyi hemen kapatır. Eğer bu kutucuk işaretliyse bot, ister varsayılan kadro ister özel koşullu müdahale olsun, Angus'un dahil olduğu **tüm savaşlarda** bu taktiği uygulayacaktır. Ancak bu seçeneği etkinleştirmeden önce, Angus'un enerjisinin %100 dolu olduğundan emin ol.`

**Geliştiriciden Tiyo: Bot neden sık sık oyunu duraklatıyor ve nasıl %100 otonom hale getirilir?**

İlk çalıştırmalarda sıkça karşılaşılan bir durum: Titanların canı görsel olarak gayet iyi görünse de bot sürekli oyunu duraklatır, bir SOS penceresi açar ve ne yapacağını sorar. Sanki sebepsiz yere panikliyor gibi görünebilir.

Bunun nedeni tamamen ana ekranda bulunan **"HP Kayıp Deltası"** ayarıdır.
Delta, tek bir savaşta alınan ani ve büyük hasara karşı bir korumadır. Örneğin Deltayı %30 olarak ayarladın. Titanin savaşa %100 canla girip %69 canla çıkarsa (%31 kayıp), %69 hala yeşil bar olsa ve hayati bir tehlike olmasa bile bot anında duracaktır.

**SOS pencereleriyle uğraşmayı bırakıp botu nasıl tamamen bağımsız yapabilirsin:**

1. **"Delta" değerini gevşet (üşenmeyenler için):** Sık sık müdahale edilmesinden sıkıldıysan ve titanlarına güveniyorsan, "HP Kayıp Deltası" değerini %100'e kadar yükselt (yani bir nevi devre dışı bırak). Bu durumda bot tek bir savaştaki hasarı hesaplamayı bırakır ve *sadece* "HP Panik Eşiği"ne odaklanır; yani can değeri gerçekten kritik bir sınıra (örneğin %25'in altına) düşene kadar durmaz.

2. **Duruşları tecrübeye dönüştür:** Her SOS penceresi, Kurallar Sihirbazı'na gidip yeni bir koşul oluşturman için bir fırsattır; böylece bot bir dahaki sefere bu hasardan nasıl kaçınacağını bilir.

3. **Analitiği Kullan (Tam Otonomiye Giden Yol):** En önemlisi de bu! Her oyun oturumundan sonra mutlaka "Analiz" sekmesine gir ve log analizini başlat. Bot kendisi kalıpları bulacak ve sana **"Altın Kurallar"** (başarısı kanıtlanmış kazanan kadrolar) önerecektir. Tek yapman gereken "Uygula"ya basmak.

**Özet:** Bot bu tarz 'Altın Kuralları' ve manuel koşulları ne kadar çok öğrenirse, o kadar az soru soracaktır. Zamanla senin titanlarının gelişim seviyesine uygun mükemmel bir bilgi tabanı oluşturacak ve **%100 otonom** hale gelecektir!



## Bölüm 4. Erime Koruması (HP ve SOS Ayarları)

Bot, iznin olmadan titanlarını asla ölüme terk etmez. Her savaştan sonra can barlarını dikkatle inceler. "Kurallar Sihirbazı" sekmesinde iki önemli güvenlik ayarı bulunur:

* **HP Panik Eşiği (örneğin, %40):** Bu mutlak sınırdır. Savaştan sonra herhangi bir titanının canı %40'ın altına düşerse bot alarm verir.
* **HP Kayıp Deltası (örneğin, %30):** Bu, ani hasar korumasıdır. Titan savaşa %100 HP ile girip %60 ile çıktıysa %40 kaybetmiştir (delta budur). Eğer tek bir savaşta en fazla %30 kayba izin verdiysen, canı hala çok olsa bile bot oyunu durdurur.

**SOS Sistemi (Kurtarma Menüsü):**
Eğer Panik, Delta tetiklendiyse veya bir titan öldüyse, bot oyunu duraklatır ve sana üç seçenekli bir pencere gösterir:
* **Elle Oyna:** Bot savaştan çekilir, savaşı sıfırlar ve odayı kendin geçersin.
* **Savaşı Geri Al:** Bot savaşı iptal eder, böylece tekrar denemek için başka bir kadro seçebilirsin.
* **Yoksay:** Bota "Her şey yolunda, bu kayıplara izin veriyorum, sonraki odaya geç" dersin.



## Bölüm 5. Telegram Bildirimleri

Bot farm yaparken sen gidip çay içebilir veya yürüyüşe çıkabilirsin. Eğer titanlar ölümün eşiğine gelirse, bot sana doğrudan Telegram üzerinden bir ekran görüntüsü ve kontrol butonları gönderir!

* **1. Adım:** Telegram'da resmi **@BotFather** botunu bul. Ona `/newbot` komutunu gönder, bir isim belirle ve uzun `Token` kodunu kopyala.
* **2. Adım:** **@getmyid_bot** botunu bul. Başlat (Start) düğmesine bas ve `Your user ID` altındaki sayıları kopyala.
* **3. Adım:** 1. Adımdaki yeni botunla olan sohbetine geri dön ve mutlaka **"BAŞLAT" (START)** butonuna tıkla.
* **4. Adım:** Programımızda "Kurallar Sihirbazı"nı aç ve **"Telegram'ı Ayarla"** butonuna bas. Token ve Chat ID bilgilerini yapıştır, "Uygula"ya ve "Profili Kaydet"e tıkla.



## Bölüm 6. Analiz ve Öğrenme

Bot, her savaşını gizli bir günlüğe kaydeder: kim kiminle dövüştü ve ne kadar HP kaldı.

"Analiz" sekmesine git ve "Log Analizini Başlat" butonuna tıkla. Bot, her kadro için Kazanma Oranını (Winrate) hesaplar. Belirli düşmanları %80 ve üzeri şansla istikrarlı bir şekilde yenen bir takım bulursa bunu **"Altın Kural"** olarak tanımlar.
"Uygula" butonuna bas; bot bu kazanan taktiği sonsuza kadar hafızasında tutacaktır!



## Bölüm 7. İstatistik ve Senkronizasyon

Bot harika istatistikler tutar: grafikler çizer, titanitleri, odaları ve iksirleri hesaplar.

**Oyun Saati Hakkında Önemli Not:**
Hero Wars oyununda yeni gün sabah saat 05:00'te başlar. Botun akşam ve gece savaşlarını karıştırmaması için Kurallar Sihirbazı'nda "Gün Sıfırlama Saati"ni mutlaka belirt.

**Akıllı Senkronizasyon:**
Diyelim ki sabah telefonda elle oynadın ve 60 titanit topladın. Akşam ise botu başlattın. Bot genel durumu nasıl anlayacak?
Çok basit! "İstatistik" sekmesine git, günü seç (Bugün) ve kutucuğa oyunda gördüğün **TOPLAM titanit miktarını** gir (örneğin 150). Bot akıllıdır: kendisinin 90 topladığını bilir, bunu 150'den çıkarır ve senin elle topladığın 60 puanı istatistiğe hassas bir şekilde ekleyerek oda ve iksir hesaplamasını buna göre günceller. Hata koruması entegredir; bot kendi topladığı miktardan daha küçük bir sayı girmene izin vermez.



## Bölüm 8. Bilgisayar Kısayolları

* **Ctrl + Q (Yumuşak Duraklatma):** Bot oyunu savaşın ortasında bırakmaz. Düşmanları güzelce alt eder, ödülü alır, bir sonraki kapının önünde durur ve bekler.
* **Ctrl + Shift + Q (Acil DURDURMA):** Botu anında kapatır. Bir şeyler ters gittiğinde bu kısayolu kullan.