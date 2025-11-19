// US States to Area Codes Mapping
const US_STATES_AREA_CODES = {
    "Alabama": ["205", "251", "256", "334", "659", "938"],
    "Alaska": ["907"],
    "Arizona": ["480", "520", "602", "623", "928"],
    "Arkansas": ["479", "501", "870"],
    "California": ["209", "213", "279", "310", "323", "408", "415", "424", "442", "510", "530", "559", "562", "619", "626", "628", "650", "657", "661", "669", "707", "714", "747", "760", "805", "818", "820", "831", "840", "858", "909", "916", "925", "949", "951"],
    "Colorado": ["303", "719", "720", "970", "983"],
    "Connecticut": ["203", "475", "860", "959"],
    "Delaware": ["302"],
    "Florida": ["239", "305", "321", "352", "386", "407", "448", "561", "645", "656", "689", "727", "754", "772", "786", "813", "850", "863", "904", "941", "954"],
    "Georgia": ["229", "404", "470", "478", "678", "706", "762", "770", "912", "943"],
    "Hawaii": ["808"],
    "Idaho": ["208", "986"],
    "Illinois": ["217", "224", "309", "312", "331", "447", "464", "618", "630", "708", "730", "773", "779", "815", "847", "872"],
    "Indiana": ["219", "260", "317", "463", "574", "765", "812", "930"],
    "Iowa": ["319", "515", "563", "641", "712"],
    "Kansas": ["316", "620", "785", "913"],
    "Kentucky": ["270", "364", "502", "606", "859"],
    "Louisiana": ["225", "318", "337", "504", "985"],
    "Maine": ["207"],
    "Maryland": ["227", "240", "301", "410", "443", "667"],
    "Massachusetts": ["339", "351", "413", "508", "617", "774", "781", "857", "978"],
    "Michigan": ["231", "248", "269", "313", "517", "586", "616", "679", "734", "810", "906", "947", "989"],
    "Minnesota": ["218", "320", "507", "612", "651", "763", "952"],
    "Mississippi": ["228", "601", "662", "769"],
    "Missouri": ["314", "417", "573", "636", "660", "816"],
    "Montana": ["406"],
    "Nebraska": ["308", "402", "531"],
    "Nevada": ["702", "725", "775"],
    "New Hampshire": ["603"],
    "New Jersey": ["201", "551", "609", "640", "732", "848", "856", "862", "908", "973"],
    "New Mexico": ["505", "575"],
    "New York": ["212", "315", "332", "347", "516", "518", "585", "607", "631", "646", "680", "716", "718", "838", "845", "914", "917", "929", "934"],
    "North Carolina": ["252", "336", "704", "743", "828", "910", "919", "980", "984"],
    "North Dakota": ["701"],
    "Ohio": ["216", "220", "234", "283", "326", "330", "380", "419", "440", "513", "567", "614", "740", "937"],
    "Oklahoma": ["405", "539", "572", "580", "918"],
    "Oregon": ["458", "503", "541", "971"],
    "Pennsylvania": ["215", "223", "267", "272", "412", "445", "484", "570", "582", "610", "717", "724", "814", "835", "878"],
    "Rhode Island": ["401"],
    "South Carolina": ["803", "821", "839", "843", "854", "864"],
    "South Dakota": ["605"],
    "Tennessee": ["423", "615", "629", "731", "865", "901", "931"],
    "Texas": ["210", "214", "254", "281", "325", "346", "361", "409", "430", "432", "469", "512", "682", "713", "726", "737", "806", "817", "830", "832", "903", "915", "936", "940", "945", "956", "972", "979"],
    "Utah": ["385", "435", "801"],
    "Vermont": ["802"],
    "Virginia": ["276", "434", "540", "571", "703", "757", "804", "826", "948"],
    "Washington": ["206", "253", "360", "425", "509", "564"],
    "West Virginia": ["304", "681"],
    "Wisconsin": ["262", "274", "414", "534", "608", "715", "920"],
    "Wyoming": ["307"]
};

let SELECTED_STATE = null;

function showStateSelection() {
    const states = Object.keys(US_STATES_AREA_CODES).sort();
    
    return `
        <div class="step-indicator">
            <div class="step-dot active"></div>
            <div class="step-dot"></div>
            <div class="step-dot"></div>
            <div class="step-dot"></div>
            <div class="step-dot"></div>
        </div>

        <p style="margin-bottom: 1.5rem; font-weight: 700; color: var(--green); font-size: 1.2rem;">
            <i class="fas fa-map-marked-alt"></i> Step 1: Choose Your State
        </p>

        <div style="margin-bottom: 2rem;">
            <label style="display: block; font-weight: 600; color: var(--green); margin-bottom: 0.75rem; font-size: 0.95rem;">
                Select Your State
            </label>
            <select id="state-dropdown" onchange="selectStateFromDropdown()" class="search-input" style="cursor: pointer; font-size: 1rem; padding: 1rem 1.5rem;">
                <option value="">-- Select a State --</option>
                ${states.map(state => `
                    <option value="${state}">${state} (${US_STATES_AREA_CODES[state].length} area code${US_STATES_AREA_CODES[state].length > 1 ? 's' : ''})</option>
                `).join('')}
            </select>
        </div>

        <div class="info-badge" style="margin-bottom: 1.5rem;">
            <i class="fas fa-shield-alt" style="font-size: 1.5rem;"></i>
            <div>
                <div style="font-weight: 700; margin-bottom: 0.25rem;">All 50 US States Available</div>
                <div style="font-size: 0.9rem;">Choose your state to see available area codes and phone numbers in your region.</div>
            </div>
        </div>

        <button onclick="proceedToAreaCodes()" id="state-next-btn" disabled class="btn btn-primary" style="width: 100%; justify-content: center; padding: 1.25rem; font-size: 1.1rem;">
            <i class="fas fa-arrow-right"></i> Next: Choose Area Code
        </button>
    `;
}

function selectStateFromDropdown() {
    const dropdown = document.getElementById('state-dropdown');
    const selectedState = dropdown.value;
    
    if (selectedState) {
        SELECTED_STATE = selectedState;
        document.getElementById('state-next-btn').disabled = false;
    } else {
        SELECTED_STATE = null;
        document.getElementById('state-next-btn').disabled = true;
    }
}

function selectState(state, event) {
    SELECTED_STATE = state;
    document.querySelectorAll('[data-state]').forEach(btn => {
        btn.classList.remove('selected');
    });
    event.target.closest('[data-state]').classList.add('selected');
    document.getElementById('state-next-btn').disabled = false;
}

function proceedToAreaCodes() {
    if (!SELECTED_STATE) {
        showToast('Please select a state', 'error');
        return;
    }

    const areaCodes = US_STATES_AREA_CODES[SELECTED_STATE];
    const areaCodeHTML = `
        <div class="step-indicator">
            <div class="step-dot completed"></div>
            <div class="step-dot active"></div>
            <div class="step-dot"></div>
            <div class="step-dot"></div>
            <div class="step-dot"></div>
        </div>

        <p style="margin-bottom: 1.5rem; font-weight: 700; color: var(--green); font-size: 1.2rem;">
            <i class="fas fa-map-marker-alt"></i> Step 2: Choose Area Code
        </p>

        <div style="margin-bottom: 1.5rem; padding: 1rem; background: var(--ivory); border-radius: 12px; display: flex; justify-content: space-between; align-items: center;">
            <div>
                <span style="color: #666; font-size: 0.85rem;">Selected State:</span>
                <strong style="color: var(--green); font-size: 1.1rem; margin-left: 0.5rem;">${SELECTED_STATE}</strong>
            </div>
            <button onclick="resetToStateSelection()" class="btn" style="padding: 0.5rem 1rem; background: white; border: 2px solid var(--green); color: var(--green); font-size: 0.85rem;">
                <i class="fas fa-undo"></i> Change State
            </button>
        </div>

        <div style="margin-bottom: 2rem;">
            <label style="display: block; font-weight: 600; color: var(--green); margin-bottom: 0.75rem; font-size: 0.95rem;">
                Select Area Code
            </label>
            <select id="area-code-dropdown" onchange="selectAreaCodeFromDropdown()" class="search-input" style="cursor: pointer; font-size: 1rem; padding: 1rem 1.5rem;">
                <option value="">-- Select an Area Code --</option>
                ${areaCodes.map(code => `
                    <option value="${code}">${code}</option>
                `).join('')}
            </select>
        </div>

        <div class="info-badge" style="margin-bottom: 1.5rem;">
            <i class="fas fa-robot" style="font-size: 1.5rem;"></i>
            <div>
                <div style="font-weight: 700; margin-bottom: 0.25rem;">AI Call Screening Included</div>
                <div style="font-size: 0.9rem;">Every number comes with 24/7 AI protection that automatically screens calls, blocks scams, and protects you from fraud.</div>
            </div>
        </div>

        <button onclick="searchNumbers()" id="search-btn" disabled class="btn btn-primary" style="width: 100%; justify-content: center; padding: 1.25rem; font-size: 1.1rem;">
            <i class="fas fa-search"></i> Search Available Numbers
        </button>
    `;

    document.getElementById('step-area-code').innerHTML = areaCodeHTML;
}

function selectAreaCodeFromDropdown() {
    const dropdown = document.getElementById('area-code-dropdown');
    const selectedCode = dropdown.value;
    
    if (selectedCode) {
        SELECTED_AREA_CODE = selectedCode;
        document.getElementById('search-btn').disabled = false;
    } else {
        SELECTED_AREA_CODE = null;
        document.getElementById('search-btn').disabled = true;
    }
}

function resetToStateSelection() {
    SELECTED_STATE = null;
    SELECTED_AREA_CODE = null;
    document.getElementById('step-area-code').innerHTML = showStateSelection();
}

function initializeProvisionModal() {
    const stepAreaCode = document.getElementById('step-area-code');
    if (stepAreaCode) {
        stepAreaCode.innerHTML = showStateSelection();
    }
}
