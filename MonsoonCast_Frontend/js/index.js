const API_BASE = window.MONSOON_API_BASE || "https://broadness-uncouth-pruning.ngrok-free.dev";

const CROPS = ["Rice", "Cotton", "Soybean", "Pigeon pea (Arhar)"];
const LEAD_BUCKETS = ["7d", "14d", "21d", "30d"];
const RISK_COLORS = { onset: "#4575b4", active: "#1a9850", break: "#d73027", revival: "#91bfdb", normal: "#bdbdbd" };

function imdCategory(mmValue) {
  const mm = Number(mmValue || 0);
  if (mm >= 204.5) return "Extremely heavy";
  if (mm >= 115.6) return "Very heavy";
  if (mm >= 64.5) return "Heavy";
  if (mm >= 15.6) return "Rather heavy";
  if (mm >= 2.5) return "Moderate";
  return "Light / dry";
}

const LOCATION_DATA_BASE = "https://raw.githubusercontent.com/pranshumaheshwari/indian-cities-and-villages/master/By%20States/";
const LOCATION_CACHE_PREFIX = "monsoon_location_state_v1:";
const STATE_NAMES = [
  "Andaman & Nicobar Islands", "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar",
  "Chandigarh", "Chhattisgarh", "Dadra & Nagar Haveli", "Daman & Diu", "Delhi", "Goa",
  "Gujarat", "Haryana", "Himachal Pradesh", "Jammu & Kashmir", "Jharkhand", "Karnataka",
  "Kerala", "Lakshadweep", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya",
  "Mizoram", "Nagaland", "Odisha", "Puducherry", "Punjab", "Rajasthan", "Sikkim",
  "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal"
];

const state = {
  hierarchy: null,
  selectedState: null,
  selectedDistrict: null,
  selectedBlock: null,
  selectedVillage: null,
  location: null,
  language: localStorage.getItem("monsoon_language") || "en",
  locationReady: false,
  date: null,
  step: 0,
  mapLeadBucket: "7d",
  apiAvailable: false,
  forecast: null,
  outlook: null,
  advisories: null,
  riskLayer: null,
  geocodeBusy: false,
  geoLastRequestAt: 0,
};

const $ = id => document.getElementById(id);
const els = {
  status: $("statusText"),
  location: $("selectedLocation"),
  locationStatus: $("locationStatus"),
  locationReadyBadge: $("locationReadyBadge"),
  languageSelect: $("languageSelect"),
  findLocationBtn: $("findLocationBtn"),
  stateInput: $("stateInput"),
  districtInput: $("districtInput"),
  blockInput: $("blockInput"),
  panchayatInput: $("panchayatInput"),
  stateOptions: $("stateOptions"),
  langModal: $("langModal"),
  districtOptions: $("districtOptions"),
  blockOptions: $("blockOptions"),
  panchayatOptions: $("panchayatOptions"),
  selectedPlaceDetails: $("selectedPlaceDetails"),
  selectedPlaceText: $("selectedPlaceText"),
  selectedCoordsText: $("selectedCoordsText"),
  cropInput: $("cropInput"),
  cropOptions: $("cropOptions"),
  cropLockNote: $("cropLockNote"),
  date: $("dateSelect"),
  dayLocationRequired: $("dayLocationRequired"),
  dayForecastContent: $("dayForecastContent"),
  hourlyForecast: $("hourlyForecast"),
  leadTime: $("leadTime"),
  dayRainValue: $("dayRainValue"),
  rainClass: $("rainClass"),
  metric3h: $("metric3h"),
  metric24h: $("metric24h"),
  metricProbability: $("metricProbability"),
  metricDryRisk: $("metricDryRisk"),
  dayDescription: $("dayDescription"),
  allDaysLocationRequired: $("allDaysLocationRequired"),
  allDaysContent: $("allDaysContent"),
  dailyList: $("dailyList"),
  overviewTotalRain: $("overviewTotalRain"),
  overviewWetDays: $("overviewWetDays"),
  overviewDryDays: $("overviewDryDays"),
  overviewHeavyDays: $("overviewHeavyDays"),
  overallPattern: $("overallPattern"),
  overallPatternDetail: $("overallPatternDetail"),
  cropList: $("cropList"),
  mapOverlayInfo: $("mapOverlayInfo"),
  mapLeadBucket: $("mapLeadBucket"),
  messageMeBtn: $("messageMeBtn"),
  subCropsContainer: $("subCropsContainer"),
  subscribeModal: $("subscribeModal"),
  cancelSubBtn: $("cancelSubBtn"),
  submitSubBtn: $("submitSubBtn"),
  sendOtpBtn: $("sendOtpBtn"),
  subOtp: $("subOtp"),
  otpSection: $("otpSection"),
};

const UI_TEXT = {
  en: {
    subtitle: "Panchayat-scale rainfall outlook",
    messageMe: "Message Me",
    subTitle: "Daily Advisory",
    subDesc: "You will receive daily advisory on what is going to happen and what you should do for the next week then next week up to 4th week.",
    subPlatform: "Choose how to receive messages",
    subCrops: "Select crop(s) for updates",
    subPhoneLbl: "Enter your number",
    cancel: "Cancel", 
    submit: "Subscribe",
    selectLocation: "Select a location",
    startHere: "Start here",
    locationAndCrops: "Location & crops",
    yourLocation: "Your location",
    dayDescription1: "Heavy rainfall indicated for this window. Avoid field work immediately before the peak; check for waterlogging risk.",
    dayDescription2: "Moderate rainfall indicated for this window. Avoid field work immediately before the peak; check for waterlogging risk.",
    dayDescription3: "Light rainfall indicated for this window. Field work can be done, but check for waterlogging risk.",
    dayDescription4: "Little to no rainfall indicated for this window. Field work can be done.",
    chooseLocationMsg: "Choose how to set your location",
    notSelected: "Not selected",
    ready: "Ready",
    useLocation: "Use my location",
    findVillageAuto: "Find your current village automatically",
    orSelectManually: "or select manually",
    state: "State",
    district: "District",
    block: "Block / Sub-district",
    panchayat: "Panchayat / Village",
    selectedPlace: "Selected place",
    chooseCrop: "Choose a crop",
    cropAdvisory: "Crop advisory",
    cropAdvisoryDesc: "Selecting a crop will generate its advisory from the 30-day outlook for your selected location.",
    crop: "Crop",
    selectLocFirst: "Select your location first.",
    cropIntroText: "Location names are loaded from the selected state's administrative dataset. The final place is geocoded only after you choose it; the selected coordinates are then sent to the forecast backend.",
    every3Hours: "Every 3 hours",
    dayForecast: "Day forecast",
    selectLocInCrops: "Select your location in Crops first.",
    dayForecastAppear: "The day forecast will appear here after the forecast and outlook have finished loading.",
    rainAtSelectedTime: "Rain at selected time",
    threeHourForecast: "3-hour forecast",
    tapATime: "Tap a time",
    threeHourRain: "3-hour rain",
    next24h: "Next 24h",
    rainProb: "Rain probability",
    dryRisk: "Dry-spell risk",
    rainfallOutlook: "Rainfall outlook",
    chooseForecastDay: "Choose a forecast day and tap a 3-hour window.",
    thirtyDayOverview: "30-day overview",
    allDays: "All days",
    thirtyDaySummaryAppear: "The 30-day rainfall summary will appear here after your location is ready.",
    totalRain: "Total rain",
    aboveAvgDays: "Above-average days",
    drySpellDays: "Break / dry-spell days",
    heavyRainDays: "Heavy-rain days",
    overallPattern: "Overall pattern",
    loadingThirtyDaySummary: "Loading the 30-day rainfall summary…",
    sixKmRainfall: "6 km rainfall field",
    map: "Map",
    reset: "Reset",
    legendOnset: "Onset",
    legendActive: "Active",
    legendBreak: "Break",
    legendRevival: "Revival",
    mapBehavior: "Map behavior",
    mapBehaviorText: "The map uses the precomputed GeoJSON risk field. Farmer weather and advisory requests remain location-specific.",
    day: "Day",
    crops: "Crops",
    sendOtp: "Send OTP",
    subOtpLbl: "Enter 6-Digit Verification Code",
    week1: "Week 1",
    week2: "Week 2",
    week3: "Week 3",
    week4: "Week 4",
    outlook: "Outlook",
    overallPatternDetail: 'Over the next 30 days, the strongest model signal is "{signal}" ({signalPct}). 7-day dry-spell risk is {drySpellPct}.',
    "Extremely heavy": "Extremely heavy",
    "Very heavy": "Very heavy",
    "Heavy": "Heavy",
    "Rather heavy": "Rather heavy",
    "Moderate": "Moderate",
    "Light / dry": "Light / dry",
    "low risk": "low risk",
    "moderate risk": "moderate risk",
    "high risk": "high risk",
    onsetLikely: "Onset Likely",
    activeRain: "Active Rain",
    drySpellRisk: "Dry-Spell Risk",
    revivalAfterBreak: "Revival After Break",
    normalConditions: "Normal Conditions",
    onset: "Onset",
    active: "Active",
    break: "Break",
    revival: "Revival",
    subTitle: "Daily Advisory",
    messageMeBtn: "Message Me",
    crop_rice: "Rice",
    crop_wheat: "Wheat",
    crop_cotton: "Cotton",
    crop_soybean: "Soybean",
    crop_maize: "Maize",
    crop_sugarcane: "Sugarcane",
    crop_pigeon_pea: "Pigeon pea pulse(Arhar)"
  },
  hi: {
    subtitle: "पंचायत-स्तरीय बारिश का अनुमान",
    selectLocation: "स्थान चुनें",
    startHere: "यहाँ शुरू करें",
    subDesc: "आपको अगले सप्ताह और फिर अगले सप्ताह तक 4वें सप्ताह के लिए क्या होने वाला है और आपको क्या करना चाहिए, इस पर दैनिक सलाह प्राप्त होगी।",
    locationAndCrops: "स्थान और फसलें",
    yourLocation: "आपका स्थान",
    chooseLocationMsg: "अपना स्थान निर्धारित करने का तरीका चुनें",
    subplatform: "संदेश प्राप्त करने का तरीका चुनें",
    cancel: "रद्द करें",
    submit: "जमा करें",
    notSelected: "चयनित नहीं",
    subPhoneLbl: "अपना नंबर दर्ज करें",
    ready: "तैयार",
    dayDescription1: "इस विंडो के लिए भारी वर्षा का संकेत दिया गया है। पीक से ठीक पहले खेत का काम करने से बचें; जलभराव के जोखिम की जांच करें।",
    dayDescription2: "इस विंडो के लिए मध्यम वर्षा का संकेत दिया गया है। पीक से ठीक पहले खेत का काम करने से बचें; जलभराव के जोखिम की जांच करें।",
    dayDescription3: "इस विंडो के लिए हल्की वर्षा का संकेत दिया गया है। खेत का काम किया जा सकता है, लेकिन जलभराव के जोखिम की जांच करें।",
    dayDescription4: "इस विंडो के लिए बहुत कम या कोई वर्षा का संकेत नहीं दिया गया है। खेत का काम किया जा सकता है।",
    useLocation: "मेरी लोकेशन का उपयोग करें",
    findVillageAuto: "अपना वर्तमान गाँव स्वचालित रूप से खोजें",
    orSelectManually: "या स्वयं चुनें",
    state: "राज्य",
    district: "जिला",
    block: "ब्लॉक / उप-जिला",
    panchayat: "पंचायत / गाँव",
    selectedPlace: "चयनित स्थान",
    chooseCrop: "फसल चुनें",
    cropAdvisory: "फसल सलाह",
    cropAdvisoryDesc: "फसल चुनने से आपके चयनित स्थान के लिए 30 दिनों के दृष्टिकोण से इसकी सलाह उत्पन्न होगी।",
    crop: "फसल",
    selectLocFirst: "पहले अपना स्थान चुनें।",
    cropIntroText: "स्थान के नाम चयनित राज्य के प्रशासनिक डेटासेट से लोड किए जाते हैं।",
    every3Hours: "हर 3 घंटे में",
    dayForecast: "दिन का पूर्वानुमान",
    selectLocInCrops: "पहले फसलों में अपना स्थान चुनें।",
    dayForecastAppear: "पूर्वानुमान और दृष्टिकोण लोड होने के बाद दिन का पूर्वानुमान यहाँ दिखाई देगा।",
    rainAtSelectedTime: "चयनित समय पर बारिश",
    threeHourForecast: "3-घंटे का पूर्वानुमान",
    tapATime: "समय पर टैप करें",
    threeHourRain: "3-घंटे की बारिश",
    next24h: "अगले 24 घंटे",
    rainProb: "बारिश की संभावना",
    dryRisk: "शुष्क दौर का जोखिम",
    rainfallOutlook: "वर्षा का दृष्टिकोण",
    chooseForecastDay: "पूर्वानुमान का दिन चुनें और 3 घंटे की खिड़की पर टैप करें।",
    thirtyDayOverview: "30-दिन का अवलोकन",
    allDays: "सभी दिन",
    thirtyDaySummaryAppear: "स्थान तैयार होने के बाद 30 दिनों की बारिश का सारांश यहाँ दिखाई देगा।",
    totalRain: "कुल बारिश",
    aboveAvgDays: "औसत से अधिक वाले दिन",
    drySpellDays: "सूखे वाले दिन",
    heavyRainDays: "भारी बारिश वाले दिन",
    overallPattern: "समग्र पैटर्न",
    loadingThirtyDaySummary: "30-दिन की बारिश का सारांश लोड हो रहा है…",
    sixKmRainfall: "6 किमी वर्षा क्षेत्र",
    map: "मानचित्र",
    reset: "रीसेट",
    legendOnset: "शुरुआत",
    legendActive: "सक्रिय",
    legendBreak: "ब्रेक",
    legendRevival: "पुनरुद्धार",
    mapBehavior: "मानचित्र का व्यवहार",
    mapBehaviorText: "मानचित्र पहले से गणना किए गए भू-स्थानिक जोखिम क्षेत्र का उपयोग करता है।",
    day: "दिन",
    crops: "फसलें",
    subCrops: "अपडेट के लिए फसलें चुनें",
    sendOtp: "OTP भेजें",
    subOtpLbl: "6-अंकीय सत्यापन कोड दर्ज करें",
    week1: "सप्ताह 1",
    week2: "सप्ताह 2",
    week3: "सप्ताह 3",
    week4: "सप्ताह 4",
    outlook: "पूर्वानुमान",
    overallPatternDetail: 'अगले 30 दिनों में, सबसे मजबूत मॉडल संकेत "{signal}" ({signalPct}) है। 7-दिवसीय शुष्क अवधि का जोखिम {drySpellPct} है।',
    "Extremely heavy": "अत्यधिक भारी बारिश",
    "Very heavy": "बहुत भारी बारिश",
    "Heavy": "भारी बारिश",
    "Rather heavy": "बल्कि भारी बारिश",
    "Moderate": "मध्यम वर्षा",
    "Light / dry": "हल्की/सूखी",
    "low risk": "कम जोखिम",
    "moderate risk": "मध्यम जोखिम",
    "high risk": "उच्च जोखिम",
    onsetLikely: "आगमन संभावित",
    activeRain: "सक्रिय बारिश",
    drySpellRisk: "सूखा दौर का जोखिम",
    revivalAfterBreak: "ब्रेक के बाद पुनरुद्धार",
    normalConditions: "सामान्य स्थिति",
    onset: "आगमन",
    active: "सक्रिय",
    break: "विराम",
    revival: "वापसी",
    subTitle: "दैनिक सलाह",
    messageMeBtn: "मुझे संदेश भेजें",
    crop_rice: "धान",
    crop_wheat: "गेहूं",
    crop_cotton: "कपास",
    crop_soybean: "सोयाबीन",
    crop_maize: "मक्का",
    crop_sugarcane: "गन्ना",
    crop_pigeon_pea: "अरहर"
  },
  or: {
    subtitle: "ପଞ୍ଚାୟତ-ସ୍ତରୀୟ ବର୍ଷା ପୂର୍ବାନୁମାନ",
    selectLocation: "ସ୍ଥାନ ବାଛନ୍ତୁ",
    startHere: "ଏଠାରୁ ଆରମ୍ଭ କରନ୍ତୁ",
    locationAndCrops: "ସ୍ଥାନ ଏବଂ ଫସଲ",
    yourLocation: "ଆପଣଙ୍କ ସ୍ଥାନ",
    subDesc: "ଆପଣଙ୍କୁ ଦୈନିକ ପରାମର୍ଶ ମିଳିବ କି ଆଗାମୀ ସପ୍ତାହରେ କ'ଣ ହେବ ଏବଂ ଆପଣଙ୍କୁ କ'ଣ କରିବା ଉଚିତ, ପରେ 4ଥ ସପ୍ତାହ ପର୍ଯ୍ୟନ୍ତ।",
    chooseLocationMsg: "ଆପଣଙ୍କ ସ୍ଥାନ ସେଟ୍ କରିବାକୁ ବାଛନ୍ତୁ",
    notSelected: "ଚୟନ ହୋଇନାହିଁ",
    ready: "ପ୍ରସ୍ତୁତ",
    subPlatform: "ସନ୍ଦେଶ ପାଇବା ପାଇଁ ଉପାୟ ବାଛନ୍ତୁ",
    subPhoneLbl: "ଆପଣଙ୍କର ନମ୍ବର ପ୍ରବେଶ କରନ୍ତୁ",
    useLocation: "ମୋର ସ୍ଥାନ ବ୍ୟବହାର କରନ୍ତୁ",
    findVillageAuto: "ସ୍ବୟଂଚାଳିତ ଭାବରେ ଆପଣଙ୍କର ବର୍ତ୍ତମାନର ଗାଁ ଖୋଜନ୍ତୁ",
    orSelectManually: "କିମ୍ବା ନିଜେ ବାଛନ୍ତୁ",
    state: "ରାଜ୍ୟ",
    cancel: "ବାତିଲ୍‌ କରନ୍ତୁ",
    submit: "ଜମା କରନ୍ତୁ",
    dayDescription1: "ଏହି ଖିଡ଼କି ପାଇଁ ପ୍ରବଳ ବର୍ଷାର ସୂଚନା ମିଳିଛି। ଶୀର୍ଷ ସମୟ ପୂର୍ବରୁ କ୍ଷେତ୍ର କାମ କରିବାକୁ ବଞ୍ଚନ୍ତୁ; ପାଣି ଭରିବାର ଆଶଙ୍କା ପାଇଁ ଯାଞ୍ଚ କରନ୍ତୁ।",
    dayDescription2: "ଏହି ଖିଡ଼କି ପାଇଁ ମଧ୍ୟମ ବର୍ଷାର ସୂଚନା ମିଳିଛି। ଶୀର୍ଷ ସମୟ ପୂର୍ବରୁ କ୍ଷେତ୍ର କാമ കാണാൻ പ്രത്യേകം വേണ്ടത്; ജലഭരാവ് ജോധിക്ക് പരിഗണനയുടെയുള്ളത്.",
    dayDescription3: "ଏହି ଖିଡ଼କି ପାଇଁ ହଲ୍କୀ ବର୍ଷାର ସୂଚନା ମିଳିଛି। କ୍ଷେତ୍ର କാമ ചെയ്യാൻ പ്രത്യേകം വേണ്ടത്; ജലഭരാവ് ജോധിക്ക് പരിഗണനയുടെയുള്ളത്.",
    dayDescription4: "ଏହି ଖିଡ଼କି ପାଇଁ କମ୍ ବର୍ଷା କିମ୍ବା କୌଣସି ବର୍ଷାର ସୂଚନା ମିଳିନାହିଁ। କ୍ଷେତ୍ର କାମ ചെയ്യാൻ പ്രത്യേകം വേണ്ടത്.",
    district: "ଜିଲ୍ଲା",
    block: "ବ୍ଲକ୍ / ଉପ-ଜିଲ୍ଲା",
    panchayat: "ପଞ୍ଚାୟତ / ଗାଁ",
    subCrops: "ଅଦ୍ୟତନ ପାଇଁ ଫସଲ ବାଛନ୍ତୁ",
    selectedPlace: "ଚୟନିତ ସ୍ଥାନ",
    chooseCrop: "ଫସଲ ବାଛନ୍ତୁ",
    cropAdvisory: "ଫସଲ ପରାମର୍ଶ",
    cropAdvisoryDesc: "ଗୋଟିଏ ଫସଲ ଚୟନ କରିବା ଦ୍ୱାରା ଆପଣଙ୍କର ଚୟନିତ ସ୍ଥାନ ପାଇଁ 30-ଦିନର ପୂର୍ବାନୁମାନରୁ ଏହାର ପରାମର୍ଶ ମିଳିବ।",
    crop: "ଫସଲ",
    selectLocFirst: "ପ୍ରଥମେ ଆପଣଙ୍କର ସ୍ଥାନ ବାଛନ୍ତୁ।",
    cropIntroText: "ସ୍ଥାନର ନାମଗୁଡିକ ମନୋନୀତ ରାଜ୍ୟର ପ୍ରଶାସନିକ ଡାଟାସେଟରୁ ଲୋଡ୍ ହୋଇଛି।",
    every3Hours: "ପ୍ରତ୍ୟେକ 3 ଘଣ୍ଟାରେ",
    dayForecast: "ଦିନର ପୂର୍ବାନୁମାନ",
    selectLocInCrops: "ପ୍ରଥମେ ଫସଲରେ ଆପଣଙ୍କର ସ୍ଥାନ ବାଛନ୍ତୁ।",
    dayForecastAppear: "ପୂର୍ବାନୁମାନ ଲୋଡ୍ ହେବା ପରେ ଦିନର ପୂର୍ବାନୁମାନ ଏଠାରେ ଦେଖାଯିବ।",
    rainAtSelectedTime: "ଚୟନିତ ସମୟରେ ବର୍ଷା",
    threeHourForecast: "3-ଘଣ୍ଟାର ପୂର୍ବାନୁମାନ",
    tapATime: "ସମୟ ଉପରେ ଟ୍ୟାପ୍ କରନ୍ତୁ",
    threeHourRain: "3-ଘଣ୍ଟାର ବର୍ଷା",
    next24h: "ଆଗାମୀ 24 ଘଣ୍ଟା",
    rainProb: "ବର୍ଷାର ସମ୍ଭାବନା",
    dryRisk: "ଶୁଖିଲା ସମୟର ଆଶଙ୍କା",
    rainfallOutlook: "ବର୍ଷାର ପୂର୍ବାନୁମାନ",
    chooseForecastDay: "ଗୋଟିଏ ପୂର୍ବାନୁମାନ ଦିନ ବାଛନ୍ତୁ ଏବଂ 3-ଘଣ୍ଟାର ୱିଣ୍ଡୋ ଟ୍ୟାପ୍ କରନ୍ତୁ।",
    thirtyDayOverview: "30-ଦିନର ସମୀକ୍ଷା",
    allDays: "ସମସ୍ତ ଦିନ",
    thirtyDaySummaryAppear: "ଆପଣଙ୍କ ସ୍ଥାନ ପ୍ରସ୍ତୁତ ହେବା ପରେ 30-ଦିନର ବର୍ଷା ସାରାଂଶ ଏଠାରେ ଦେଖାଯିବ।",
    totalRain: "ମୋଟ ବର୍ଷା",
    aboveAvgDays: "ହାରାହାରିଠାରୁ ଅଧିକ ଦିନ",
    drySpellDays: "ଶୁଖିଲା ଦିନ",
    heavyRainDays: "ପ୍ରବଳ ବର୍ଷାର ଦିନ",
    overallPattern: "ସମଗ୍ର ପ୍ୟାଟର୍ନ",
    loadingThirtyDaySummary: "30-ଦିନର ବର୍ଷା ସାରାଂଶ ଲୋଡ୍ ହେଉଛି…",
    sixKmRainfall: "6 କିମି ବର୍ଷା କ୍ଷେତ୍ର",
    map: "ମାନଚିତ୍ର",
    reset: "ରିସେଟ୍",
    legendOnset: "ଆରମ୍ଭ",
    legendActive: "ସକ୍ରିୟ",
    legendBreak: "ବିରତି",
    legendRevival: "ପୁନରୁଦ୍ଧାର",
    mapBehavior: "ମାନଚିତ୍ରର ବ୍ୟବହାର",
    mapBehaviorText: "ମାନଚିତ୍ର ଗଣନା କରାଯାଇଥିବା ଜିଓ-ଜେସନ୍ ବିପଦ କ୍ଷେତ୍ର ବ୍ୟବହାର କରେ।",
    day: "ଦିନ",
    crops: "ଫସଲ",
    sendOtp: "OTP ପଠାନ୍ତୁ",
    subOtpLbl: "6-ଅଙ୍କ ବିଶିଷ୍ଟ ଯାଞ୍ଚ କୋଡ୍ ପ୍ରବେଶ କରନ୍ତୁ",
    week1: "ସପ୍ତାହ 1",
    week2: "ସପ୍ତାହ 2",
    week3: "ସପ୍ତାହ 3",
    week4: "ସପ୍ତାହ 4",
    outlook: "ପୂର୍ବାନୁମାନ",
    overallPatternDetail: 'ଅଗଲେ 30 ଦିନୋଂ ମେ, ସବସେ ମଜବୁତ ମୋଡ଼ଲ ସଙ୍କେତ "{signal}" ({signalPct}) ଅଛି। 7-ଦିଵସୀୟ ଶୁଷ୍କ ଅବധି କା ଜୋଘିମ {drySpellPct} ଅଛି।',
    "Extremely heavy": "ଅତ୍ୟନ୍ତ ପ୍ରବଳ",
    "Very heavy": "ଅତ୍ୟଧିକ ପ୍ରବଳ",
    "Heavy": "ପ୍ରବଳ",
    "Rather heavy": "ତୁଳନାମୂଳକ ଭାବେ ପ୍ରବଳ",
    "Moderate": "ମଧ୍ୟମ",
    "Light / dry": "ହାଲୁକା / ଶୁଖିଲା",
    "low risk": "କମ ଜୋଘିମ",
    "moderate risk": "ମଧ୍ୟମ ଜୋଘିମ",
    "high risk": "ଉଚ୍ଚ ଜୋଘିମ",
    onsetLikely: "ଆଗମନ ସମ୍ଭାବନା",
    activeRain: "ସକ୍ରିୟ ବର୍ଷା",
    drySpellRisk: "ଶୁଖିଲା ସମୟର ଆଶଙ୍କା",
    revivalAfterBreak: "ବିରତି ପରେ ପୁନରୁଦ୍ଧାର",
    normalConditions: "ସାଧାରଣ ପରିସ୍ଥିତି",
    onset: "ଆଗମନ",
    active: "ସକ୍ରିୟ",
    break: "ବିରାମ",
    revival: "ପ୍ରତ୍ୟାବର୍ତ୍ତନ",
    subTitle: "ଦୈନିକ ପରାମର୍ଶ",
    messageMeBtn: "ମୋତେ ମେସେଜ୍ କରନ୍ତୁ",
    crop_rice: "ଧାନ",
    crop_wheat: "ଗହମ",
    crop_cotton: "କପା",
    crop_soybean: "ସୋୟାବିନ୍",
    crop_maize: "ମକା",
    crop_sugarcane: "ଆଖୁ",
    crop_pigeon_pea: "ପିଜନ୍ ପି (ଆରହାର)"
  }
};

const RISK_LABELS = { onset: t("onsetLikely"), active: t("activeRain"), break: t("drySpellRisk"), revival: t("revivalAfterBreak"), normal: t("normalConditions") };
const map = L.map("map", { zoomControl: true, attributionControl: true }).setView([21.15, 81.30], 7);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 14, attribution: "© OpenStreetMap contributors" }).addTo(map);

function t(key) { return UI_TEXT[state.language]?.[key] || UI_TEXT.en[key] || key; }

function setLanguage(language) { 
  if (!UI_TEXT[language]) { language = "en"; } 
  state.language = language;
  localStorage.setItem("monsoon_language", language); 
  renderLanguage(); 
}

function renderLanguage() {
  els.languageSelect.value = state.language;
  
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const key = el.getAttribute("data-i18n");
    if (key && UI_TEXT[state.language]?.[key]) {
      el.textContent = UI_TEXT[state.language][key];
    }
  });
}

function mm(v) { return `${Number(v || 0).toFixed(1)} mm`; }
function pct(v) { return `${Math.round(Number(v || 0) * 100)}%`; }
function timeOfDay(iso) { return iso.slice(11, 16); }
function formatDate(dateStr) { return new Date(`${dateStr}T00:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" }); }
function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[ch]));
}
function locationLabel(loc) {
  if (!loc) return t("selectLocation");
  return loc.name || `${Number(loc.latitude).toFixed(2)}°N, ${Number(loc.longitude).toFixed(2)}°E`;
}

async function fetchJSON(pathname) {
  const res = await fetch(`${API_BASE}${pathname}`, {
    headers: { "ngrok-skip-browser-warning": "true" }
  });
  if (!res.ok) throw new Error(`HTTP ${res.status} on ${pathname}`);
  const text = await res.text();
  try { return JSON.parse(text); }
  catch { throw new Error(`Non-JSON response from ${pathname}`); }
}

function setStatus(text) { els.status.textContent = text; }
function setLocationUi(message, ready = false) {
  els.locationStatus.textContent = message;
  els.locationReadyBadge.textContent = ready ? t("ready") : t("notSelected");
  els.locationReadyBadge.classList.toggle("ready", ready);
  els.location.textContent = locationLabel(state.location);
}

function populateDatalist(datalist, values) {
  datalist.innerHTML = (values || [])
    .filter(Boolean)
    .map(value => `<option value="${escapeHtml(value)}"></option>`)
    .join("");
}

function exactMatch(input, values) {
  const value = input.value.trim();
  return (values || []).find(v => v.toLowerCase() === value.toLowerCase()) || null;
}

function clearInput(input, datalist, placeholder, disabled = true) {
  input.value = "";
  input.disabled = disabled;
  input.placeholder = placeholder;
  datalist.innerHTML = "";
}

function resetBelowState() {
  state.hierarchy = state.selectedState ? state.hierarchy : null;
  state.selectedDistrict = null;
  state.selectedBlock = null;
  state.selectedVillage = null;
  clearInput(els.districtInput, els.districtOptions, "Choose a district", true);
  clearInput(els.blockInput, els.blockOptions, "Choose a block", true);
  clearInput(els.panchayatInput, els.panchayatOptions, "Choose a panchayat / village", true);
}

function resetLocationData() {
  state.location = null;
  state.locationReady = false;
  state.forecast = null;
  state.outlook = null;
  state.advisories = null;
  els.selectedPlaceDetails.hidden = true;
  els.cropInput.value = "";
  els.messageMeBtn.disabled = true;
  els.cropInput.disabled = true;
  els.cropLockNote.textContent = t("selectLocFirst");
  els.date.innerHTML = "";
  els.date.disabled = true;
  els.dayForecastContent.hidden = true;
  els.dayLocationRequired.hidden = false;
  els.allDaysContent.hidden = true;
  els.allDaysLocationRequired.hidden = false;
  els.cropList.innerHTML = "";
  setLocationUi(t("chooseLocationMsg"), false);
}

async function loadStateDataset(stateName) {
  const cacheKey = `${LOCATION_CACHE_PREFIX}${stateName}`;
  try {
    const cached = localStorage.getItem(cacheKey);
    if (cached) return JSON.parse(cached);
  } catch (err) {
    console.warn("Location cache read failed:", err);
  }

  const url = `${LOCATION_DATA_BASE}${encodeURIComponent(stateName)}.json`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Could not load location data for ${stateName}`);
  const data = await res.json();

  try { localStorage.setItem(cacheKey, JSON.stringify(data)); }
  catch (err) { console.warn("Location cache write failed:", err); }
  return data;
}

function getDistrictNames() {
  return (state.hierarchy?.districts || []).map(d => d.district).sort((a, b) => a.localeCompare(b));
}
function getDistrictObject(name) {
  return (state.hierarchy?.districts || []).find(d => d.district.toLowerCase() === name.toLowerCase()) || null;
}
function getBlockNames() {
  const district = getDistrictObject(state.selectedDistrict);
  return (district?.subDistricts || []).map(d => d.subDistrict).sort((a, b) => a.localeCompare(b));
}
function getBlockObject(name) {
  const district = getDistrictObject(state.selectedDistrict);
  return (district?.subDistricts || []).find(d => d.subDistrict.toLowerCase() === name.toLowerCase()) || null;
}
function getVillageNames() {
  return ((getBlockObject(state.selectedBlock)?.villages) || []).slice().sort((a, b) => a.localeCompare(b));
}

async function handleStateChange() {
  const selected = exactMatch(els.stateInput, STATE_NAMES);
  resetLocationData();
  resetBelowState();
  if (!selected) {
    state.selectedState = null;
    state.hierarchy = null;
    if (els.stateInput.value.trim()) setLocationUi("Choose a listed state.", false);
    return;
  }

  state.selectedState = selected;
  setStatus("LOADING LOCATIONS");
  setLocationUi(`Loading districts for ${selected}…`, false);
  try {
    state.hierarchy = await loadStateDataset(selected);
    populateDatalist(els.districtOptions, getDistrictNames());
    els.districtInput.disabled = false;
    els.districtInput.placeholder = "Type or choose a district";
    setLocationUi(`Districts ready for ${selected}`, false);
    setStatus(state.apiAvailable ? "LIVE" : "READY");
  } catch (err) {
    console.warn("State dataset load failed:", err);
    setLocationUi("Could not load this state's location list.", false);
    setStatus("LOCATION DATA ERROR");
  }
}

async function handleDistrictChange() {
  const selected = exactMatch(els.districtInput, getDistrictNames());
  state.selectedDistrict = selected;
  state.selectedBlock = null;
  state.selectedVillage = null;
  resetLocationDataButKeepHierarchy();
  clearInput(els.blockInput, els.blockOptions, "Choose a block", true);
  clearInput(els.panchayatInput, els.panchayatOptions, "Choose a panchayat / village", true);

  if (!selected) {
    if (els.districtInput.value.trim()) setLocationUi("Choose a listed district.", false);
    return;
  }
  populateDatalist(els.blockOptions, getBlockNames());
  els.blockInput.disabled = false;
  els.blockInput.placeholder = "Type or choose a block";
  setLocationUi(`${selected} selected — choose a block`, false);
}

function resetLocationDataButKeepHierarchy() {
  state.location = null;
  state.locationReady = false;
  state.forecast = null;
  state.outlook = null;
  state.advisories = null;
  els.selectedPlaceDetails.hidden = true;
  els.cropInput.value = "";
  els.messageMeBtn.disabled = true;
  els.cropInput.disabled = true;
  els.cropLockNote.textContent = t("selectLocFirst");
  els.date.innerHTML = "";
  els.date.disabled = true;
  els.dayForecastContent.hidden = true;
  els.dayLocationRequired.hidden = false;
  els.allDaysContent.hidden = true;
  els.allDaysLocationRequired.hidden = false;
  els.cropList.innerHTML = "";
  els.location.textContent = t("selectLocation");
}

function handleBlockChange() {
  const selected = exactMatch(els.blockInput, getBlockNames());
  state.selectedBlock = selected;
  state.selectedVillage = null;
  resetLocationDataButKeepHierarchy();
  clearInput(els.panchayatInput, els.panchayatOptions, "Choose a panchayat / village", true);

  if (!selected) {
    if (els.blockInput.value.trim()) setLocationUi("Choose a listed block.", false);
    return;
  }
  populateDatalist(els.panchayatOptions, getVillageNames());
  els.panchayatInput.disabled = false;
  els.panchayatInput.placeholder = "Type or choose a panchayat / village";
  setLocationUi(`${selected} selected — choose a panchayat / village`, false);
}

async function handleVillageChange() {
  const selected = exactMatch(els.panchayatInput, getVillageNames());

  state.selectedVillage = selected;
  resetLocationDataButKeepHierarchy();
  state.selectedVillage = selected;

  if (!selected) {
    if (els.panchayatInput.value.trim()) {
      setLocationUi("Choose a listed panchayat / village.", false);
    }
    return;
  }

  setLocationUi(`Finding coordinates for ${selected}…`, false);
  setStatus("LOCATING");
  els.panchayatInput.disabled = true;

  await createLocationFromPlace(null, {
    village: selected,
    block: state.selectedBlock,
    district: state.selectedDistrict,
    stateName: state.selectedState,
  });
}

async function geocodePlace(detail) {
  const attempts = [
    `${detail.village}, ${detail.block}, ${detail.district}, ${detail.stateName}, India`,
    `${detail.village}, ${detail.district}, ${detail.stateName}, India`,
    `${detail.village}, ${detail.stateName}, India`
  ];

  for (const query of attempts) {
    const cacheKey = `monsoon_geocode_v2:${query.toLowerCase()}`;

    try {
      const cached = localStorage.getItem(cacheKey);
      if (cached) return JSON.parse(cached);
    } catch (err) {
      console.warn("Geocode cache read failed:", err);
    }

    const elapsed = Date.now() - state.geoLastRequestAt;
    if (elapsed < 1100) {
      await new Promise(resolve => setTimeout(resolve, 1100 - elapsed));
    }

    state.geoLastRequestAt = Date.now();

    try {
      const url = "https://nominatim.openstreetmap.org/search?" + new URLSearchParams({
        format: "jsonv2",
        q: query,
        countrycodes: "in",
        limit: "3",
        addressdetails: "1",
      });

      const res = await fetch(url, { headers: { "Accept-Language": "en" } });
      if (!res.ok) {
        console.warn(`Geocoder HTTP ${res.status} for "${query}"`);
        continue;
      }

      const data = await res.json();
      if (!data.length) {
        console.warn(`No result for "${query}"`);
        continue;
      }

      const result = data.find(item =>
        item.address && (item.address.village || item.address.hamlet || item.address.town || item.address.city)
      ) || data[0];

      const output = {
        latitude: Number(result.lat),
        longitude: Number(result.lon),
        display_name: result.display_name
      };

      try { localStorage.setItem(cacheKey, JSON.stringify(output)); } 
      catch (err) { console.warn("Geocode cache write failed:", err); }

      return output;
    } catch (err) {
      console.warn(`Geocoder request failed for "${query}"`, err);
    }
  }

  throw new Error(`No coordinates found for ${detail.village}, ${detail.district}, ${detail.stateName}`);
}

async function reverseGeocode(lat, lon) {
  const cacheKey = `monsoon_reverse_v1:${lat.toFixed(5)},${lon.toFixed(5)}`;
  try {
    const cached = localStorage.getItem(cacheKey);
    if (cached) return JSON.parse(cached);
  } catch (err) {
    console.warn("Reverse-geocode cache read failed:", err);
  }

  const elapsed = Date.now() - state.geoLastRequestAt;
  if (elapsed < 1100) await new Promise(resolve => setTimeout(resolve, 1100 - elapsed));
  state.geoLastRequestAt = Date.now();

  const url = "https://nominatim.openstreetmap.org/reverse?" + new URLSearchParams({
    format: "jsonv2",
    lat: String(lat),
    lon: String(lon),
    zoom: "10",
    addressdetails: "1",
  });
  const res = await fetch(url, { headers: { "Accept-Language": "en" } });
  if (!res.ok) throw new Error(`Reverse geocoder HTTP ${res.status}`);
  const data = await res.json();
  const result = { display_name: data.display_name || `${lat.toFixed(2)}°, ${lon.toFixed(2)}°` };
  try { localStorage.setItem(cacheKey, JSON.stringify(result)); }
  catch (err) { console.warn("Reverse-geocode cache write failed:", err); }
  return result;
}

async function createLocationFromPlace(label, detail) {
  try {
    const geo = await geocodePlace(detail);
    await finalizeLocation({
      latitude: geo.latitude,
      longitude: geo.longitude,
      name: detail?.village ? `${detail.village}, ${detail.block}` : geo.display_name,
      source: "manual",
      hierarchy: detail,
    });
  } catch (err) {
    console.warn("Forward geocoding failed:", err);
    els.panchayatInput.disabled = false;
    setStatus("LOCATION ERROR");
    setLocationUi(`Could not find coordinates for ${detail?.village || "this place"}.`, false);
  }
}

function ensureLocationPermission(onGranted) {
  if (!(window.cordova && cordova.plugins && cordova.plugins.permissions)) {
    onGranted();
    return;
  }
  const permissions = cordova.plugins.permissions;
  permissions.checkPermission(
    permissions.ACCESS_FINE_LOCATION,
    status => {
      if (status.hasPermission) onGranted();
      else permissions.requestPermission(
        permissions.ACCESS_FINE_LOCATION,
        reqStatus => {
          if (reqStatus.hasPermission) onGranted();
          else {
            alert("Location permission was denied.");
            setStatus("LOCATION DENIED");
          }
        },
        err => {
          console.warn("Permission request failed:", err);
          alert("Unable to request location permission.");
          setStatus("PERMISSION ERROR");
        }
      );
    },
    err => {
      console.warn("Permission check failed:", err);
      alert("Unable to check location permission.");
      setStatus("PERMISSION ERROR");
    }
  );
}

function getCurrentPosition() {
  return new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(
      resolve,
      firstError => {
        console.warn("Fast location attempt failed:", firstError);
        navigator.geolocation.getCurrentPosition(
          resolve,
          reject,
          { enableHighAccuracy: true, timeout: 30000, maximumAge: 300000 }
        );
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
    );
  });
}

async function handleFindLocation() {
  if (!navigator.geolocation) {
    alert("Geolocation is not supported by this device.");
    return;
  }

  ensureLocationPermission(async () => {
    els.findLocationBtn.disabled = true;
    setStatus("GETTING GPS");
    setLocationUi("Getting your current location…", false);

    try {
      const position = await getCurrentPosition();
      const lat = position.coords.latitude;
      const lon = position.coords.longitude;

      let placeName = `${lat.toFixed(2)}°N, ${lon.toFixed(2)}°E`;
      try {
        const reverse = await reverseGeocode(lat, lon);
        placeName = reverse.display_name;
      } catch (err) {
        console.warn("Reverse geocoding failed:", err);
      }

      state.selectedState = null;
      state.selectedDistrict = null;
      state.selectedBlock = null;
      state.selectedVillage = null;

      els.stateInput.value = "";
      clearInput(els.districtInput, els.districtOptions, "Choose a district", true);
      clearInput(els.blockInput, els.blockOptions, "Choose a block", true);
      clearInput(els.panchayatInput, els.panchayatOptions, "Choose a panchayat / village", true);

      await finalizeLocation({ latitude: lat, longitude: lon, name: placeName, source: "gps" });
    } catch (error) {
      console.warn("Geolocation failed:", error);
      let message = "Unable to retrieve your location.";
      if (error.code === 1) message = "Location permission was denied. Please allow location access for MonsoonCast.";
      else if (error.code === 2) message = "Your location could not be determined. Please move near a window or use manual location.";
      else if (error.code === 3) message = "Location is taking too long. Please try again or use manual location.";

      alert(message);
      setStatus(state.apiAvailable ? "LIVE" : "READY");
      setLocationUi(t("chooseLocationMsg"), false);
    } finally {
      els.findLocationBtn.disabled = false;
    }
  });
}

async function finalizeLocation(location) {
  state.location = location;
  state.locationReady = false;
  state.forecast = null;
  state.outlook = null;
  state.advisories = null;
  els.selectedPlaceDetails.hidden = false;
  els.selectedPlaceText.textContent = locationLabel(location);
  els.selectedCoordsText.textContent = `${Number(location.latitude).toFixed(5)}°, ${Number(location.longitude).toFixed(5)}°`;
  els.cropInput.value = "";
  els.cropInput.disabled = true;
  els.cropLockNote.textContent = "Preparing weather forecast…";
  els.messageMeBtn.disabled = false;
  els.dayLocationRequired.hidden = false;
  els.dayForecastContent.hidden = true;
  els.allDaysLocationRequired.hidden = false;
  els.allDaysContent.hidden = true;
  setLocationUi("Location selected — preparing forecast…", false);

  setStatus("FORECASTING");
  const forecastOK = await loadForecast();
  if (!forecastOK) {
    setLocationUi("Forecast could not be loaded. Try this location again.", false);
    els.cropLockNote.textContent = "Forecast unavailable — choose the location again.";
    return;
  }

  setStatus("CALCULATING OUTLOOK");
  const outlookOK = await loadOutlook();
  if (!outlookOK) {
    setLocationUi("Forecast ready; outlook could not be loaded.", false);
    els.cropLockNote.textContent = "Outlook unavailable — try the location again.";
    return;
  }

  state.locationReady = true;
  setStatus("LIVE");
  setLocationUi(locationLabel(location), true);
  els.cropInput.disabled = false;
  els.cropLockNote.textContent = t("chooseCrop");
  els.dayLocationRequired.hidden = true;
  els.dayForecastContent.hidden = false;
  els.allDaysLocationRequired.hidden = true;
  els.allDaysContent.hidden = false;
  renderDay();
  renderAllDays();
}

async function loadForecast() {
  if (!state.location) return false;
  try {
    state.forecast = await fetchJSON(`/forecast?latitude=${state.location.latitude}&longitude=${state.location.longitude}`);
  } catch (err) {
    console.warn("Forecast unavailable:", err);
    state.forecast = null;
    return false;
  }

  const days = state.forecast?.days || [];
  const dates = days.map(d => d.date);
  els.date.innerHTML = dates.map(d => `<option value="${escapeHtml(d)}">${escapeHtml(formatDate(d))}</option>`).join("");
  els.date.disabled = !dates.length;
  if (dates.length) {
    state.date = dates.includes(state.date) ? state.date : dates[0];
    els.date.value = state.date;
  }
  renderDay();
  renderAllDays();
  return dates.length > 0;
}

function currentDay() {
  if (!state.forecast) return null;
  return state.forecast.days.find(d => d.date === state.date) || state.forecast.days[0] || null;
}

function renderDay() {
  const day = currentDay();
  if (!day) return;
  const points = day.forecast?.length ? day.forecast : [{ time: `${day.date}T00:00:00`, rain_mm: day.rain_mm, rain_probability: day.rain_probability_max }];
  state.step = Math.min(state.step, points.length - 1);
  const selected = points[state.step];

  els.leadTime.textContent = timeOfDay(selected.time);
  els.dayRainValue.textContent = mm(selected.rain_mm);
  els.rainClass.textContent = t(imdCategory(selected.rain_mm));
  els.metric3h.textContent = mm(selected.rain_mm);
  els.metric24h.textContent = mm(day.rain_mm);
  els.metricProbability.textContent = selected.rain_probability != null ? pct(selected.rain_probability) : "—";
  const breakProb7d = state.outlook?.outlook?.["7d"]?.break;
  els.metricDryRisk.textContent = breakProb7d != null ? pct(breakProb7d) : "—";

  els.dayDescription.textContent = selected.rain_mm >= 64.5
    ? t("dayDescription1")
    : selected.rain_mm >= 15.6
      ? t("dayDescription2")
      : selected.rain_mm >= 2.5
        ? t("dayDescription3")
        : t("dayDescription4");

  els.hourlyForecast.innerHTML = points.map((p, i) => {
    const active = i === state.step ? "active" : "";
    const rain = Number(p.rain_mm || 0);
    return `<button class="hour-card ${active}" type="button" data-step="${i}" role="listitem">
      <span class="hour-time">${escapeHtml(timeOfDay(p.time))}</span>
      <span class="hour-icon">${rain >= 35 ? "⛈" : rain >= 8 ? "🌧" : "☁"}</span>
      <strong>${rain.toFixed(1)}<small> mm</small></strong>
      <span class="hour-prob">${p.rain_probability != null ? pct(p.rain_probability) : "—"}</span>
    </button>`;
  }).join("");

  els.hourlyForecast.querySelectorAll(".hour-card").forEach(btn => {
    btn.addEventListener("click", () => {
      state.step = Number(btn.dataset.step);
      renderDay();
    });
  });
}

function renderAllDays() {
  const days = state.forecast?.days || [];
  if (!days.length) return;
  const total = days.reduce((a, d) => a + Number(d.rain_mm || 0), 0);
  const wet = days.filter(d => Number(d.rain_mm || 0) >= 2.5).length;
  const dry = days.filter(d => Number(d.rain_mm || 0) < 2.5).length;
  const heavy = days.filter(d => Number(d.rain_mm || 0) >= 64.5).length;
  els.overviewTotalRain.textContent = mm(total);
  els.overviewWetDays.textContent = wet;
  els.overviewDryDays.textContent = dry;
  els.overviewHeavyDays.textContent = heavy;

  els.dailyList.innerHTML = days.map(d => `<article class="daily-row card">
      <div class="daily-date"><strong>${escapeHtml(formatDate(d.date))}</strong><span>${escapeHtml(d.date)}</span></div>
      <div class="daily-bar-wrap">
        <div class="daily-bar"><span style="width:${Math.min(100, (Number(d.rain_mm || 0) / 120) * 100)}%"></span></div>
        <div class="daily-tags"><span class="tag">${escapeHtml(t(imdCategory(d.rain_mm)))}</span></div>
      </div>
      <div class="daily-mm">${mm(d.rain_mm)}</div>
    </article>`).join("");
}

async function loadOutlook() {
  if (!state.location) return false;
  try {
    state.outlook = await fetchJSON(`/outlook?latitude=${state.location.latitude}&longitude=${state.location.longitude}`);
  } catch (err) {
    console.warn("Outlook unavailable:", err);
    state.outlook = null;
    return false;
  }
  renderOutlook();
  renderDay();
  return Boolean(state.outlook?.outlook);
}

function renderOutlook() {
  if (!state.outlook) return;
  const bucket30 = state.outlook.outlook?.["30d"];
  if (bucket30) {
    const dominant = Object.entries(bucket30).sort((a, b) => b[1] - a[1])[0];
    els.overallPattern.textContent = RISK_LABELS[dominant[0]] || dominant[0];
    //els.overallPatternDetail.textContent = `Over the next 30 days, the strongest model signal is "${(RISK_LABELS[dominant[0]] || dominant[0]).toLowerCase()}" (${pct(dominant[1])}). 7-day dry-spell risk is ${pct(state.outlook.outlook?.["7d"]?.break)}.`;
    els.overallPatternDetail.textContent = t("overallPatternDetail")
      .replace("{signal}", RISK_LABELS[dominant[0]] || dominant[0].toLowerCase())
      .replace("{signalPct}", pct(dominant[1]))
      .replace("{drySpellPct}", pct(state.outlook.outlook?.["7d"]?.break));
  }
}

async function loadAdvisoryForCrop(crop) {
  if (!state.locationReady || !state.location || !crop) return;
  state.advisories = null;
  els.cropList.innerHTML = `<div class="card crop-loading"><span class="eyebrow">Calculating advisory</span><strong>${escapeHtml(crop)} · 7 / 14 / 21 / 30 days</strong></div>`;
  setStatus("ADVISORY");
  try {
    state.advisories = await fetchJSON(`/advisory?latitude=${state.location.latitude}&longitude=${state.location.longitude}&crops=${encodeURIComponent(crop)}`);
    setStatus("LIVE");
  } catch (err) {
    console.warn("Advisory unavailable:", err);
    state.advisories = null;
    els.cropList.innerHTML = `<div class="card location-required"><strong>Advisory unavailable.</strong><p>Check the server connection and try selecting the crop again.</p></div>`;
    setStatus("ADVISORY ERROR");
    return;
  }
  renderCrops();
}

function renderCrops() {
  const advisories = state.advisories?.advisories || [];
  if (!advisories.length) {
    els.cropList.innerHTML = "";
    return;
  }

  els.cropList.innerHTML = LEAD_BUCKETS.map(bucket => {
    const row = advisories.find(a => a.lead_bucket === bucket);
    const c = row?.crop;
    const cropKey = c === "Pigeon pea (Arhar)" ? "crop_pigeon_pea" : "crop_" + c.toLowerCase();
    if (!row) return "";
    return `<div class="lead-group">
      <div class="lead-group-title">${bucket === '7d' ? t("week1") : bucket === '14d' ? t("week2") : bucket === '21d' ? t("week3") : t("week4")} ${t("outlook")}</div>
      <article class="crop-card card">
        <div class="crop-top">
          <div><div class="crop-name">${escapeHtml(t(cropKey))}</div><div class="crop-window">Kharif</div></div>
          <span class="action-badge risk-${escapeHtml(row.risk_level)}">${escapeHtml(t(row.risk_level+" risk"))}</span>
        </div>
        <div class="crop-action">${escapeHtml(row.text?.[state.language] || row.text?.en || "—")}</div>
        <div class="crop-rain">
          <div><span>${escapeHtml(t("onset"))}</span><strong>${pct(row.probabilities?.onset)}</strong></div>
          <div><span>${escapeHtml(t("active"))}</span><strong>${pct(row.probabilities?.active)}</strong></div>
          <div><span>${escapeHtml(t("break"))}</span><strong>${pct(row.probabilities?.break)}</strong></div>
          <div><span>${escapeHtml(t("revival"))}</span><strong>${pct(row.probabilities?.revival)}</strong></div>
        </div>
      </article>
    </div>`;
  }).join("");
}

async function loadRiskMap() {
  els.mapOverlayInfo.textContent = `Risk map · ${state.mapLeadBucket} outlook`;
  let geojson;
  try {
    geojson = await fetchJSON(`/risk-map?lead_bucket=${state.mapLeadBucket}`);
  } catch (err) {
    console.warn("Risk map unavailable:", err);
    els.mapOverlayInfo.textContent = "Risk map unavailable — check the API connection.";
    return;
  }
  if (state.riskLayer) map.removeLayer(state.riskLayer);
  state.riskLayer = L.geoJSON(geojson, {
    style: feature => ({ color: feature.properties.color, weight: 1, fillColor: feature.properties.color, fillOpacity: 0.55 }),
    onEachFeature: (feature, layer) => {
      const p = feature.properties;
      layer.bindTooltip(
        `<strong>${escapeHtml(RISK_LABELS[p.dominant_risk] || p.dominant_risk)}</strong> (${escapeHtml(pct(p.confidence))})<br>` +
        `Grid ${escapeHtml(p.grid_key)}<br>` +
        Object.entries(p.probabilities || {}).map(([k, v]) => `${escapeHtml(RISK_LABELS[k] || k)}: ${escapeHtml(pct(v))}`).join("<br>"),
        { sticky: true }
      );
    }
  }).addTo(map);
  if (geojson.features?.length) map.fitBounds(state.riskLayer.getBounds(), { padding: [24, 24], maxZoom: 11 });
}

function setupTabs() {
  document.querySelectorAll(".tab-btn").forEach(btn => btn.addEventListener("click", () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.toggle("active", b === btn));
    document.querySelectorAll(".tab-panel").forEach(panel => panel.classList.toggle("active", panel.dataset.tab === tab));
    if (tab === "map") setTimeout(() => map.invalidateSize(), 80);
  }));
}

function setupControls() {
  populateDatalist(els.stateOptions, STATE_NAMES);
  populateDatalist(els.cropOptions, CROPS);

  els.findLocationBtn.addEventListener("click", handleFindLocation);
  els.stateInput.addEventListener("change", handleStateChange);
  els.stateInput.addEventListener("blur", () => {
    if (els.stateInput.value.trim()) handleStateChange();
  });
  els.districtInput.addEventListener("change", handleDistrictChange);
  els.districtInput.addEventListener("blur", () => { if (els.districtInput.value.trim()) handleDistrictChange(); });
  els.blockInput.addEventListener("change", handleBlockChange);
  els.blockInput.addEventListener("blur", () => { if (els.blockInput.value.trim()) handleBlockChange(); });
  els.panchayatInput.addEventListener("change", handleVillageChange);
  
  els.languageSelect.addEventListener("change", (event) => {
    setLanguage(event.target.value);
    renderCrops();
  });
  
  els.messageMeBtn.addEventListener("click", () => {
    els.subCropsContainer.innerHTML = CROPS.map(c => {
      const cropKey = c === "Pigeon pea (Arhar)" ? "crop_pigeon_pea" : "crop_" + c.toLowerCase();
      const translatedCrop = t(cropKey) || c;
      return `<label class="custom-checkbox"><input type="checkbox" value="${escapeHtml(c)}"> <span>${escapeHtml(translatedCrop)}</span></label>`;
    }).join("");
    els.subscribeModal.hidden = false;
  });

  els.cancelSubBtn.addEventListener("click", () => els.subscribeModal.hidden = true);

  els.sendOtpBtn.addEventListener("click", async () => {
    const phone = $("subPhone").value.replace(/\D/g, "");
    if (phone.length !== 10) return alert("Please enter a valid 10-digit phone number.");
    
    els.sendOtpBtn.disabled = true;
    els.sendOtpBtn.textContent = "Sending...";
    
    try {
      const res = await fetch(`${API_BASE}/request-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: phone })
      });
    
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to send OTP.");
    
      alert("OTP sent to your phone via WhatsApp.");
      els.otpSection.hidden = false;
      
      // Cooldown timer for resending OTP
      let cooldown = 60;
      const interval = setInterval(() => {
        els.sendOtpBtn.textContent = `Resend (${cooldown}s)`;
        cooldown--;
        if (cooldown < 0) {
          clearInterval(interval);
          els.sendOtpBtn.disabled = false;
          els.sendOtpBtn.textContent = "Resend OTP";
        }
      }, 1000);
    
    } catch (err) {
      alert(err.message);
      els.sendOtpBtn.disabled = false;
      els.sendOtpBtn.textContent = "Send OTP";
    }
  });
  
  // Handle Submit with OTP
  els.submitSubBtn.addEventListener("click", async () => {
    const sms = $("chkSms").checked;
    const wa = $("chkWa").checked;
    const platform = (sms && wa) ? 3 : (wa ? 2 : (sms ? 1 : 0));
    if (platform === 0) return alert("Please select SMS or WhatsApp.");
  
    const selectedCrops = Array.from(els.subCropsContainer.querySelectorAll("input:checked")).map(cb => cb.value);
    if (!selectedCrops.length) return alert("Please select at least one crop.");
  
    const phone = $("subPhone").value.replace(/\D/g, "");
    if (phone.length !== 10) return alert("Please enter a valid 10-digit number.");
  
    const otp = els.subOtp.value.trim();
    if (!otp || otp.length !== 6) return alert("Please enter the 6-digit OTP code.");
  
    els.submitSubBtn.disabled = true;
  
    try {
      const res = await fetch(`${API_BASE}/subscribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          phone: phone,
          otp: otp,
          platform: platform,
          crops: selectedCrops,
          language: state.language,
          latitude: state.location.latitude,
          longitude: state.location.longitude
        })
      });
    
      const data = await res.json();
      if (!res.ok) return alert(data.detail || "Subscription failed.");
    
      alert(data.action === "updated" ? "Preferences updated successfully!" : "Subscribed successfully!");
      els.subscribeModal.hidden = true;
    } catch (e) {
      alert("Subscription failed. Check connection.");
    } finally {
      els.submitSubBtn.disabled = false;
      els.submitSubBtn.textContent = t("submit");
    }
  });

  els.cropInput.addEventListener("change", () => {
    const crop = exactMatch(els.cropInput, CROPS);
    if (!crop) {
      if (els.cropInput.value.trim()) els.cropLockNote.textContent = "Choose one of the listed crops.";
      return;
    }
    loadAdvisoryForCrop(crop);
  });
  els.cropInput.addEventListener("blur", () => {
    if (els.cropInput.value.trim()) {
      const crop = exactMatch(els.cropInput, CROPS);
      if (crop) loadAdvisoryForCrop(crop);
    }
  });

  els.date.addEventListener("change", () => { state.date = els.date.value; state.step = 0; renderDay(); });

  if (els.mapLeadBucket) {
    els.mapLeadBucket.addEventListener("change", () => {
      state.mapLeadBucket = els.mapLeadBucket.value;
      loadRiskMap();
    });
  }

  const mapReset = $("mapReset");
  if (mapReset) mapReset.addEventListener("click", () => {
    if (state.riskLayer?.getBounds()?.isValid()) map.fitBounds(state.riskLayer.getBounds(), { padding: [24, 24], maxZoom: 11 });
    else map.setView([21.15, 81.30], 7);
  });

  document.querySelectorAll(".lang-choice-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const selectedLang = btn.dataset.lang;
      setLanguage(selectedLang);
      renderCrops();
      els.langModal.hidden = true;
    });
  });
}

async function boot() {
  setupTabs();
  setupControls();
  if(!localStorage.getItem("monsoon_language")){
    els.langModal.hidden = false;
  }
  renderLanguage();
  resetLocationData();

  try {
    await fetchJSON("/health");
    state.apiAvailable = true;
    setStatus("LIVE");
    loadRiskMap();
  } catch (err) {
    state.apiAvailable = false;
    setStatus("OFFLINE");
  }
}
boot();