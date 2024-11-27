// tfbrew.js
// Main Vue App for TFBrew Fermentation Controller

const app = Vue.createApp({
  data() {
    return {
      controllers: {},
      systemWs: null,
      fridgeWs: null,
      heaterWs: null,
      menuOpen: false,
      controllerState: Vue.reactive ({
        temperature: 0,
        w1Temperature: 0,
        specificGravity: 0,
        abv: 0,
        atten: 0,
        originalGravity: 0,
        fridgeEnabled: false,
        fridgeAutomatic: false,
        fridgePower: 0,
        fridgeSetpoint: 0,
        heaterEnabled: false,
        heaterAutomatic: false,
        heaterPower: 0,
        heaterSetpoint: 0,
      }),
      formattedDateTime: '',
      dateTimeInterval: null,
      numpadVisible: false,
      numpadValue: '',
      numpadInputField: '',
    };
  },
  computed: {
    automaticStrFridge() {
      // Returns "Auto" or "Manual" based on fridgeAutomatic state
      return this.controllerState.fridgeAutomatic ? "Auto" : "Manual";
    },
    automaticStrHeater() {
      // Returns "Auto" or "Manual" based on heaterAutomatic state
      return this.controllerState.heaterAutomatic ? "Auto" : "Manual";
    },
    enabledStrFridge() {
      // Returns "Enabled" or "Disabled" based on fridgeEnabled state
      return this.controllerState.fridgeEnabled ? "Enabled" : "Disabled";
    },
    enabledStrHeater() {
      // Returns "Enabled" or "Disabled" based on heaterEnabled state
      return this.controllerState.heaterEnabled ? "Enabled" : "Disabled";
    },
    fridgeButtonStyle() {
      // Style for the fridge button, changing color based on power
      return {
        color: this.controllerState.fridgePower === 100 ? "#3399ff" : "#d3d3d3",
        fontSize: "40px",
      };
    },
    heaterButtonStyle() {
      // Style for the heater button, changing color based on power
      return {
        color: this.controllerState.heaterPower === 100 ? "#cc0000" : "#d3d3d3",
        fontSize: "40px",
      };
    },
    formattedABV() {
      // Returns ABV formatted to 2 decimal places or '-'
      return this.controllerState.abv !== null && this.controllerState.abv !== undefined
        ? this.controllerState.abv.toFixed(2)
        : "-";
    },
    formattedAtten() {
      // Returns attenuation formatted to 2 decimal places or '-'
      return this.controllerState.atten !== null && this.controllerState.atten !== undefined
        ? this.controllerState.atten.toFixed(2)
        : "-";
    },
    formattedGravity() {
      // Returns specific gravity formatted to 4 decimal places or '-'
      return this.controllerState.specificGravity !== null && this.controllerState.specificGravity !== undefined
        ? this.controllerState.specificGravity.toFixed(4)
        : "-";
    },
    formattedOriginalGravity() {
      // Returns original gravity formatted to 4 decimal places or '-'
      return this.controllerState.originalGravity !== null && this.controllerState.originalGravity !== undefined
        ? this.controllerState.originalGravity.toFixed(4)
        : "-";
    },
    formattedTemperature() {
      // Returns temperature formatted to 1 decimal place or '-'
      return this.controllerState.temperature !== null && this.controllerState.temperature !== undefined
        ? this.controllerState.temperature.toFixed(1)
        : "-";
    },
    formattedW1Temperature() {
      // Returns W1 temperature formatted to 1 decimal place or '-'
      return this.controllerState.w1Temperature !== null && this.controllerState.w1Temperature !== undefined
        ? this.controllerState.w1Temperature.toFixed(1)
        : "-";
    },
  },
  methods: {
    // Initialize Fridge WebSocket
    newWsConnFridge(url) {
      console.log("Initializing Fridge WebSocket with URL:", url);
      this.fridgeWs = new SockJS(url);
      this.fridgeWs.onmessage = (msg) => {
        const data = msg.data;
        console.log("Fridge WebSocket message received:", data);
        Object.assign(this.controllerState, {
          temperature: data.temperature,
          w1Temperature: data.w1temperature,
          specificGravity: data.gravity,
          abv: data.abv,
          atten: data.atten,
          originalGravity: data.ograv,
          fridgeEnabled: data.enabled,
          fridgeAutomatic: data.automatic,
          fridgePower: data.power,
          fridgeSetpoint: data.setpoint,
        });
      };
      this.fridgeWs.onclose = () => {
        console.log("Fridge WebSocket closed. Reconnecting...");
        this.newWsConnFridge(url);
      };
      this.fridgeWs.onerror = (e) => {
        console.error("Fridge WebSocket error:", e);
      };
    },
    // Initialize Heater WebSocket
    newWsConnHeater(url) {
      console.log("Initializing Heater WebSocket with URL:", url);
      this.heaterWs = new SockJS(url);
      this.heaterWs.onmessage = (msg) => {
        const data = msg.data;
        console.log("Heater WebSocket message received:", data);
        Object.assign(this.controllerState, {
          heaterEnabled: data.enabled,
          heaterAutomatic: data.automatic,
          heaterPower: data.power,
          heaterSetpoint: data.setpoint,
        });
      };
      this.heaterWs.onclose = () => {
        console.log("Heater WebSocket closed. Reconnecting...");
        this.newWsConnHeater(url);
      };
      this.heaterWs.onerror = (e) => {
        console.error("Heater WebSocket error:", e);
      };
    },
    // Toggles fridge power between 0 and 100
    togglePower(type) {
      const key = `${type.toLowerCase()}Power`;
      const newPower = this.controllerState[key] === 100 ? 0 : 100;
      this.controllerState[key] = newPower;
      this.updatePower(newPower, type);
    },
    // Send power update to backend
    updatePower(power, type) {
      const ws = type === "Fridge" ? this.fridgeWs : this.heaterWs;
      if (ws?.readyState === SockJS.OPEN) {
        ws.send(JSON.stringify({ power }));
      } else {
        console.error(`${type} WebSocket is not open.`);
      }
    },
    // Send state update to backend
    toggleState(key, type) {
      const ws = type === "Fridge" ? this.fridgeWs : this.heaterWs;
      const mappedKey = key.endsWith("Enabled") ? "enabled" : "automatic";
      if (ws?.readyState === SockJS.OPEN) {
        const newState = !this.controllerState[key];
        this.controllerState[key] = newState;
        console.log("toggleState Sending:", mappedKey, newState);
        ws.send(JSON.stringify({ [mappedKey]: newState }));
      } else {
        console.error(`${type} WebSocket is not open.`);
      }
    },
    // Update controller temperature setpoint and send to backend
    updateSetpoint(value, type) {
      const ws = type === "Fridge" ? this.fridgeWs : this.heaterWs;
      if (ws?.readyState === SockJS.OPEN) {
        this.controllerState[`${type.toLowerCase()}Setpoint`] = value;
        ws.send(JSON.stringify({ setpoint: value }));
      } else {
        console.error(`${type} WebSocket is not open.`);
      }
    },
    // Reload page
    reloadPage() {
      window.location.reload();
    },
    // Open the chart page
    openCharts() {
      window.open("index2.html", "_blank");
    },
    // Handle menu closing after item click
    handleMenuAction(action) {
      const actions = {
        reload: this.reloadPage,
        charts: this.openCharts,
        reboot: () => this.sendSystemCommand("reboot"),
        shutdown: () => this.sendSystemCommand("poweroff"),
      };
      actions[action]?.();
      this.menuOpen = false;
    },
    // Send system admin command (reboot, shutdown)
    sendSystemCommand(command) {
      if (this.systemWs?.readyState === SockJS.OPEN) {
        console.log(`Sending ${command} command`);
        //this.systemWs.send(command);
        this.systemWs.send(JSON.stringify({ admin: command }));
      } else {
        console.error("System WebSocket is not open.");
      }
    },
    // Show the numpad
    showNumpadForField(field) {
      this.numpadInputField = field;
      this.numpadValue = this.controllerState[field]?.toString() || "0";
      this.numpadVisible = true;
    },
    // Handle numpad submission to input field
    handleNumpadSubmit() {
      const numericValue = parseFloat(this.numpadValue);
      this.controllerState[this.numpadInputField] = numericValue;
      if (this.numpadInputField === "fridgeSetpoint") {
        this.updateSetpoint(numericValue, "Fridge");
      } else if (this.numpadInputField === "heaterSetpoint") {
        this.updateSetpoint(numericValue, "Heater");
      }
      this.numpadVisible = false;
    },
  },
  mounted() {
    // Establish connections to controllers and fetch details
    console.log("Fetching controller details from /controllers endpoint");
    fetch("/controllers")
      .then((response) => response.json())
      .then((data) => {
        this.controllers = data;
        if (data.Fridge) {
          fetch(data.Fridge.url)
            .then((res) => res.json())
            .then((fridgeData) => {
              this.newWsConnFridge(fridgeData.wsUrl);
            });
        }
        if (data.Heater) {
          fetch(data.Heater.url)
            .then((res) => res.json())
            .then((heaterData) => {
              this.newWsConnHeater(heaterData.wsUrl);
            });
        }
      });

    this.systemWs = new SockJS(
      "http://192.168.254.53:8080/controllers/System/ws"
    );

    // Update formatted date-time every second
    this.dateTimeInterval = setInterval(() => {
      this.formattedDateTime = new Date().toLocaleString("en-US", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hour12: true,
      });
    }, 1000);
  },
  unmounted() {
    // Clear the interval when the component is unmounted
    clearInterval(this.dateTimeInterval);
  },
  template: `
        <q-layout view="hHh lpR fFf">
          <q-page-container>
            <!-- Toolbars and Buttons Row -->
            <div class="row items-center q-pa-md" style="width: 100%; justify-content: space-between; gap: 8px;">
              <!-- Menu Button (Far Left) -->
              <q-btn-dropdown v-model="menuOpen" color="grey-9" label="Menu" class="q-pa-md q-mr-md">
                <q-list>
                  <q-item style="color: black" clickable v-ripple @click="handleMenuAction('reload')">
                    <q-item-section>Reload</q-item-section>
                  </q-item>
                  <q-item style="color: black" clickable v-ripple @click="handleMenuAction('charts')">
                    <q-item-section>Charts</q-item-section>
                  </q-item>
                  <q-separator />
                  <q-item style="color: black" clickable v-ripple @click="handleMenuAction('reboot')">
                    <q-item-section>Reboot</q-item-section>
                  </q-item>
                  <q-item style="color: black" clickable v-ripple @click="handleMenuAction('shutdown')">
                    <q-item-section>Shutdown</q-item-section>
                  </q-item>
                </q-list>
              </q-btn-dropdown>
        
              <!-- Fridge Toolbar -->
              <q-toolbar class="bg-primary text-white dense rounded-borders" style="flex: 1; padding: 4px; margin-right: 4px;">
                <q-btn flat dense color="white" :label="enabledStrFridge" style="width: 80px;" @click="toggleState('fridgeEnabled', 'Fridge')"/>
                <div style="width: 4px;"></div>
                <q-btn flat dense color="white" :label="automaticStrFridge" style="width: 80px;" @click="toggleState('fridgeAutomatic', 'Fridge')"></q-btn>
                <div style="position: relative; display: inline-block; max-width: 100px; margin-left: 4px;">
                <q-input dark dense standout v-model="controllerState.fridgeSetpoint" input-class="text-right" style="max-width: 100px; margin-left: 4px; font-size: 20px;" @click="showNumpadForField('fridgeSetpoint')">
                  <template v-slot:append>
                    <div style="font-size: 1rem; margin-right: 4px;">&deg;F</div>
                  </template>
                </q-input>
                </div>
              </q-toolbar>
        
              <!-- Heater Toolbar -->
              <q-toolbar class="bg-negative text-white dense rounded-borders" style="flex: 1; padding: 4px; margin-left: 4px;">
                <q-btn flat dense color="white" :label="enabledStrHeater" style="width: 80px;" @click="toggleState('heaterEnabled', 'Heater')"/>
                <div style="width: 8px;"></div>
                <q-btn flat dense color="white" :label="automaticStrHeater" style="width: 80px;" @click="toggleState('heaterAutomatic', 'Heater')"></q-btn>
                <div style="position: relative; display: inline-block; max-width: 100px; margin-left: 4px;">
                <q-input dark dense standout v-model="controllerState.heaterSetpoint" input-class="text-right" style="max-width: 100px; margin-left: 4px; font-size: 20px;" @click="showNumpadForField('heaterSetpoint')">
                  <template v-slot:append>
                    <div style="font-size: 1rem; margin-right: 4px;">&deg;F</div>
                  </template>
                </q-input>
                </div>
              </q-toolbar>
        
              <!-- Power Buttons (Far Right) -->
              <div class="row items-center q-ml-md" style="gap: 16px;">
                <q-btn round flat @click="togglePower('Fridge')" ><q-icon name="ac_unit" :style="fridgeButtonStyle" /></q-btn>
                <q-btn round flat @click="togglePower('Heater')" class="q-btn--inline"><q-icon name="local_fire_department" :style="heaterButtonStyle" /></q-btn>
              </div>
            </div>
        
            <!-- Centered Labels and Data Points -->
            <div class="row q-mt-md justify-center">
              <!-- First Line: Gravity and Beer Temp -->
              <div class="col-auto text-center q-mr-lg">
                <div style="font-size: 30px;">Gravity (SG)</div>
                <div style="font-size: 80px; font-weight: bold;">{{ formattedGravity }}</div>
              </div>
              <div class="col-auto text-center q-ml-lg">
                <div style="font-size: 30px;">Beer Temp (&deg;F)</div>
                <div style="font-size: 80px; font-weight: bold;">{{ formattedTemperature }}</div>
              </div>
            </div>
            <div class="row q-mt-md justify-center">
              <!-- Second Line: ABV, Atten, Fridge Temp -->
              <div class="col-auto text-center q-mr-lg">
                <div style="font-size: 24px;">ABV (%)</div>
                <div style="font-size: 70px; font-weight: bold;">{{ formattedABV }}</div>
              </div>
              <div class="col-auto text-center q-ml-lg q-mr-lg">
                <div style="font-size: 24px;">Atten (%)</div>
                <div style="font-size: 70px; font-weight: bold;">{{ formattedAtten }}</div>
              </div>
              <div class="col-auto text-center q-ml-lg">
                <div style="font-size: 24px;">Fridge Temp (&deg;F)</div>
                <div style="font-size: 70px; font-weight: bold;">{{ formattedW1Temperature }}</div>
              </div>
            </div>
          </q-page-container>

      <!-- Numpad Dialog -->
      <q-dialog v-model="numpadVisible" persistent>
        <q-card style="min-width: 300px;">
          <q-card-section>
            <div class="numpad-display text-h5 text-center">{{ numpadValue || '\u00A0' }}</div>
          </q-card-section>
          <q-card-section>
            <div class="numpad-row">
              <q-btn flat dense class="q-ma-sm" style="color: black; font-size: 1.25rem" @click="numpadValue += '1'">1</q-btn>
              <q-btn flat dense class="q-ma-sm" style="color: black; font-size: 1.25rem" @click="numpadValue += '2'">2</q-btn>
              <q-btn flat dense class="q-ma-sm" style="color: black; font-size: 1.25rem" @click="numpadValue += '3'">3</q-btn>
            </div>
            <div class="numpad-row">
              <q-btn flat dense class="q-ma-sm" style="color: black; font-size: 1.25rem" @click="numpadValue += '4'">4</q-btn>
              <q-btn flat dense class="q-ma-sm" style="color: black; font-size: 1.25rem" @click="numpadValue += '5'">5</q-btn>
              <q-btn flat dense class="q-ma-sm" style="color: black; font-size: 1.25rem" @click="numpadValue += '6'">6</q-btn>
            </div>
            <div class="numpad-row">
              <q-btn flat dense class="q-ma-sm" style="color: black; font-size: 1.25rem" @click="numpadValue += '7'">7</q-btn>
              <q-btn flat dense class="q-ma-sm" style="color: black; font-size: 1.25rem" @click="numpadValue += '8'">8</q-btn>
              <q-btn flat dense class="q-ma-sm" style="color: black; font-size: 1.25rem" @click="numpadValue += '9'">9</q-btn>
            </div>
            <div class="numpad-row">
              <q-btn flat dense class="q-ma-sm" style="color: black; font-size: 1.25rem" @click="numpadValue = ''">Clear</q-btn>
              <q-btn flat dense class="q-ma-sm" style="color: black; font-size: 1.25rem" @click="numpadValue += '0'">0</q-btn>
              <q-btn flat dense class="q-ma-sm" style="color: black; font-size: 1.25rem" @click="numpadValue.includes('.') ? '' : numpadValue += '.'">.</q-btn>
            </div>
          </q-card-section>
          <q-card-actions align="center">
            <q-btn flat dense color="primary" style="font-size: 1.25rem" @click="numpadValue = numpadValue.slice(0, -1)" label="Backspace"></q-btn>
            <q-btn flat dense color="primary" style="font-size: 1.25rem" @click="handleNumpadSubmit" label="Enter"></q-btn>
          </q-card-actions>
        </q-card>
      </q-dialog>
        
          <!-- Footer -->
          <q-footer class="bg-dark text-white q-px-md q-py-sm" elevated>
            <div class="row justify-between text-body2 items-center">
              <div>TFBrew</div>
              <div>OG: {{ formattedOriginalGravity }}</div>
              <div>{{ formattedDateTime }}</div>
            </div>
          </q-footer>
        </q-layout>
      `
});

app.use(Quasar);
app.mount('#app');

