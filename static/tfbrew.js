// filename: tfbrew.js

var chartColors = {
    red: 'rgb(255, 99, 132)',
    orange: 'rgb(255, 159, 64)',
    yellow: 'rgb(255, 205, 86)',
    green: 'rgb(34, 139, 34)',
    blue: 'rgb(54, 162, 235)',
    purple: 'rgb(153, 102, 255)',
    grey: 'rgb(201, 203, 207)',
    pink: 'rgb(255, 102, 204)',
    teal: 'rgb(64, 224, 208)',
    brown: 'rgb(165, 42, 42)',
    lime: 'rgb(0, 255, 0)',
    navy: 'rgb(0, 0, 128)',
    lightBlue: 'rgb(179, 209, 255)',
    lightRed: 'rgb(255, 179, 179)'
};
var plotComp = {
    template: `
    <div>
        <canvas ref="plot" width="400" height="350"></canvas>
    </div>
    `,
    props: ['href', 'timeRange'],
    data: function() {
        return {
            ctx: null,
            chart: null
        }
    },
    methods: {
        beerData: function(datapoint) {
            this.chart.data.labels.push(moment(datapoint.when));
            this.chart.data.datasets[0].data.push(datapoint.specificGravity);
            this.chart.data.datasets[1].data.push(datapoint.abv);
            this.chart.data.datasets[2].data.push(datapoint.atten);
            this.chart.data.datasets[3].data.push(datapoint.originalGravity);
            this.chart.update();
        },
        fetchData: function() {
            const currentTime = Date.now();
            const timeRangeInMs = this.timeRange * 60 * 1000;
            const cutoffTime = currentTime - timeRangeInMs;

            fetch(`${this.href}`)
            .then(response => response.json())
            .then(json => {
                this.chart.data.labels = [];
                this.chart.data.datasets.forEach(dataset => dataset.data = []);

                json.label.forEach((x, index) => {
                    const timestampInMs = x * 1000;
                    if (timestampInMs >= cutoffTime) {
                        this.chart.data.labels.push(timestampInMs);
                        this.chart.data.datasets[0].data.push(json.gravity[index]);
                        this.chart.data.datasets[1].data.push(json.abv[index]);
                        this.chart.data.datasets[2].data.push(json.atten[index]);
                        this.chart.data.datasets[3].data.push(json.ograv[index]);
                    }
                });

                const originalGravityValue = json.ograv[0].toFixed(4);
                this.chart.data.datasets[3].label = `OG (${originalGravityValue})`;

                this.updateChartScales();
                this.chart.update();
            });
        },
        updateChartScales: function() {
            let unit, stepSize;
            if (this.timeRange <= 60) {
                unit = 'minute';
                stepSize = 5;
                displayFormat = { minute: 'h:mm A' };
            } else if (this.timeRange <= 240) {
                unit = 'minute';
                stepSize = 15;
                displayFormat = { minute: 'h:mm A' };
            } else if (this.timeRange <= 1440) {
                unit = 'hour';
                stepSize = 1;
                displayFormat = { hour: 'h A' };
            } else {
                unit = 'hour';
                stepSize = 6;
                displayFormat = { hour: 'MMM D, h:mm A' };
            }

            this.chart.options.scales.xAxes[0].time.unit = unit;
            this.chart.options.scales.xAxes[0].time.stepSize = stepSize;
            this.chart.options.scales.xAxes[0].time.displayFormats = displayFormat;
        }
    },
    watch: {
        timeRange: function() {
            this.fetchData();
        }
    },
    mounted: function() {
        this.ctx = this.$refs.plot.getContext('2d');
        this.chart = new Chart(this.ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                {
                    label: 'Gravity',
                    fill: false,
                    backgroundColor: chartColors.yellow,
                    borderColor: chartColors.yellow,
                    data: [],
                    yAxisID: 'gravity-axis',
                    pointRadius: 0,
                    borderWidth: 1
                },
                {
                    label: 'ABV',
                    fill: false,
                    backgroundColor: chartColors.green,
                    borderColor: chartColors.green,
                    data: [],
                    yAxisID: 'abv-axis',
                    pointRadius: 0,
                    borderWidth: 1
                },
                {
                    label: 'Attenuation',
                    fill: false,
                    backgroundColor: chartColors.orange,
                    borderColor: chartColors.orange,
                    data: [],
                    yAxisID: 'atten-axis',
                    pointRadius: 0,
                    borderWidth: 1
                },
                {
                    label: 'OG',
                    fill: false,
                    backgroundColor: chartColors.purple,
                    borderColor: chartColors.purple,
                    data: [],
                    yAxisID: 'gravity-axis',
                    pointRadius: 0,
                    borderWidth: 1
                }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                legend: {
                    labels: {
                        boxWidth: 10
                    }
                },
                tooltips: {
                    mode: 'index',
                    intersect: false
                },
                scales: {
                    xAxes: [{
                        type: 'time',
                        time: {
                            unit: 'minute',
                            stepSize: 5,
                            displayFormats: {
                                minute: 'h:mm A'
                            }
                        },
                        gridLines: {
                            color: '#444444'
                        }
                    }],
                    yAxes: [{
                        beginAtZero: false,
                        position: 'left',
                        id: 'gravity-axis',
                        ticks: {
                            suggestedMin: 0.95,
                            suggestedMax: 1.25
                        },
                        gridLines: {
                            color: '#666'
                        }
                    }, {
                        beginAtZero: true,
                        position: 'right',
                        id: 'abv-axis',
                        ticks: {
                            suggestedMin: 0,
                            suggestedMax: 20
                        },
                        gridLines: {
                            color: '#444444'
                        }
                    }, {
                        beginAtZero: true,
                        position: 'right',
                        id: 'atten-axis',
                        ticks: {
                            suggestedMin: 0,
                            suggestedMax: 100
                        },
                        gridLines: {
                            color: '#444444'
                        }
                    }]
                }
            }
        });

        this.isDarkMode = true;
        document.body.classList.add('dark-mode');

        this.fetchData();
    }
};
var plotComp2 = {
    template: `
    <div>
        <canvas ref="plot" width="400" height="350"></canvas>
    </div>
    `,
    props: ['href', 'timeRange'],
    data: function() {
        return {
            ctx: null,
            chart: null
        }
    },
    methods: {
        tempData: function(datapoint) {
            this.chart.data.labels.push(moment(datapoint.when));
            this.chart.data.datasets[0].data.push(datapoint.temperature);
            this.chart.data.datasets[1].data.push(datapoint.w1Temperature);
            this.chart.data.datasets[2].data.push(datapoint.fridgeSetpoint);
            this.chart.data.datasets[3].data.push(datapoint.heaterSetpoint);
            this.chart.data.datasets[4].data.push(datapoint.fridgePower);
            this.chart.data.datasets[5].data.push(datapoint.heaterPower);
            this.chart.update();
        },
        fetchData: function() {
            const currentTime = Date.now();
            const timeRangeInMs = this.timeRange * 60 * 1000;
            const cutoffTime = currentTime - timeRangeInMs;

            fetch(`${this.href}`)
            .then(response => response.json())
            .then(json => {
                this.chart.data.labels = [];
                this.chart.data.datasets.forEach(dataset => dataset.data = []);

                json.label.forEach((x, index) => {
                    const timestampInMs = x * 1000;
                    if (timestampInMs >= cutoffTime) {
                        this.chart.data.labels.push(timestampInMs);
                        this.chart.data.datasets[0].data.push(json.temperature[index]);
                        this.chart.data.datasets[1].data.push(json.w1temperature[index]); //w1Temperature
                        this.chart.data.datasets[2].data.push(json.setpoint[index]); // fridgeSetpoint
                        this.chart.data.datasets[3].data.push(json.heater_setpoint[index]); // heaterSetpoint
                        this.chart.data.datasets[4].data.push(json.power[index]); // fridgePower
                        this.chart.data.datasets[5].data.push(json.heater_power[index]); // heaterPower
                    }
                });

                this.updateChartScales();
                this.chart.update();
            });
        },
        updateChartScales: function() {
            let unit, stepSize;
            if (this.timeRange <= 60) {
                unit = 'minute';
                stepSize = 5;
                displayFormat = { minute: 'h:mm A' };
            } else if (this.timeRange <= 240) {
                unit = 'minute';
                stepSize = 15;
                displayFormat = { minute: 'h:mm A' };
            } else if (this.timeRange <= 1440) {
                unit = 'hour';
                stepSize = 1;
                displayFormat = { hour: 'h A' };
            } else {
                unit = 'hour';
                stepSize = 6;
                displayFormat = { hour: 'MMM D, h:mm A' };
            }

            this.chart.options.scales.xAxes[0].time.unit = unit;
            this.chart.options.scales.xAxes[0].time.stepSize = stepSize;
            this.chart.options.scales.xAxes[0].time.displayFormats = displayFormat;
        }
    },
    watch: {
        timeRange: function() {
            this.fetchData();
        }
    },
    mounted: function() {
        this.ctx = this.$refs.plot.getContext('2d');
        this.chart = new Chart(this.ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                {
                    label: 'Beer Temp',
                    fill: false,
                    backgroundColor: chartColors.pink,
                    borderColor: chartColors.pink,
                    data: [],
                    yAxisID: 'temperature-axis',
                    pointRadius: 0,
                    borderWidth: 1
                },
                {
                    label: 'Fridge Temp',
                    fill: false,
                    backgroundColor: chartColors.teal,
                    borderColor: chartColors.teal,
                    data: [],
                    yAxisID: 'temperature-axis',
                    pointRadius: 0,
                    borderWidth: 1
                },
                {
                    label: 'Cold Target',
                    fill: false,
                    backgroundColor: chartColors.lightBlue,
                    borderColor: chartColors.lightBlue,
                    data: [],
                    yAxisID: 'temperature-axis',
                    pointRadius: 0,
                    borderWidth: 1
                },
                {
                    label: 'Hot Target',
                    fill: false,
                    backgroundColor: chartColors.lightRed,
                    borderColor: chartColors.lightRed,
                    data: [],
                    yAxisID: 'temperature-axis',
                    pointRadius: 0,
                    borderWidth: 1
                },
                {
                    label: 'Cold Power',
                    fill: false,
                    backgroundColor: chartColors.blue,
                    borderColor: chartColors.blue,
                    data: [],
                    yAxisID: 'power-axis',
                    pointRadius: 0,
                    borderWidth: 1,
                    hidden: true
                },
                {
                    label: 'Hot Power',
                    fill: false,
                    backgroundColor: chartColors.red,
                    borderColor: chartColors.red,
                    data: [],
                    yAxisID: 'power-axis',
                    pointRadius: 0,
                    borderWidth: 1,
                    hidden: true
                }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                legend: {
                    labels: {
                        boxWidth: 10
                    }
                },
                tooltips: {
                    mode: 'index',
                    intersect: false
                },
                scales: {
                    xAxes: [{
                        type: 'time',
                        time: {
                            unit: 'minute',
                            stepSize: 5,
                            displayFormats: {
                                minute: 'h:mm a'
                            }
                        },
                        gridLines: {
                            color: '#444444'
                        }
                    }],
                    yAxes: [{
                        beginAtZero: false,
                        position: 'left',
                        id: 'temperature-axis',
                        ticks: {
                            suggestedMin: 30,
                            suggestedMax: 120
                        },
                        gridLines: {
                            color: '#666'
                        }
                    },{
                        beginAtZero: true,
                        position: 'right',
                        id: 'power-axis',
                        ticks: {
                            min: 0,
                            max: 100,
                            stepSize: 100,
                            callback: function(value) {
                                return value === 100 ? 'On' : 'Off';
                            }
                        },
                        gridLines: {
                            color: '#444444'
                        }
                    }]
                }
            }
        });

        this.fetchData();
    }
};
var numpad = {
  template: `
    <div v-if="visible">
      <!-- Overlay -->
      <div class="overlay" @click="hideNumpad"></div>

      <!-- Numpad Modal -->
      <div class="numpad">
        <div class="numpad-display">{{ value || ' '}}</div>
        <div class="numpad-row">
          <button @click="inputNumber('1')">1</button>
          <button @click="inputNumber('2')">2</button>
          <button @click="inputNumber('3')">3</button>
        </div>
        <div class="numpad-row">
          <button @click="inputNumber('4')">4</button>
          <button @click="inputNumber('5')">5</button>
          <button @click="inputNumber('6')">6</button>
        </div>
        <div class="numpad-row">
          <button @click="inputNumber('7')">7</button>
          <button @click="inputNumber('8')">8</button>
          <button @click="inputNumber('9')">9</button>
        </div>
        <div class="numpad-row">
          <button @click="clear">Clear</button>
          <button @click="inputNumber('0')">0</button>
          <button @click="inputDecimal">.</button>
        </div>
        <div class="numpad-row">
          <button class="backspace" @click="backspace">Backspace</button>
          <button @click="submit">Enter</button>
        </div>
      </div>
    </div>
  `,
  data() {
    return {
      value: '',
      visible: false,
      inputField: ''
    };
  },
  methods: {
    inputNumber(num) {
      this.value += num;
    },
    inputDecimal() {
      if (!this.value.includes('.')) {
        this.value += '.';
      }
    },
    clear() {
      this.value = '';
    },
    backspace() {
      this.value = this.value.slice(0, -1);
    },
    submit() {
      if (this.inputField) {
        this.$emit('update', this.value);  // Emit value to parent component
      }
      this.hideNumpad();
    },
    showNumpad(inputField, value = '0') {
      this.inputField = inputField;
      this.value = value;
      this.visible = true;
    },
    hideNumpad() {
      this.visible = false;
      this.value = '';
    }
  }
};
Vue.component('brewcontroller', {
    props: ['href'],
    components: {
        'numpad': numpad,
        'plot': plotComp,
        'plot2': plotComp2
    },
    template: `
<div class="container-fluid" style="padding-top: 0; margin-top: 0; position: absolute; top: 0; width: 100%;">
    <div class="row no-gutters" style="align-items: flex-start; padding: 0; margin: 0;">
        <div class="col text-end align-self-start" style="font-size: 10px; padding: 0; margin: 0;">TFbrew</div>
    </div>
    <div class="row align-items-center no-gutters mb-1">
        <div class="col d-flex justify-content-start">
            <div class="btn-toolbar">
                <div class="btn-group me-1">
                    <button class="btn btn-secondary" @click="rebootSystem" style="border: none; color: #262626; font-size: 20px; width: 80px;">
                        Reboot
                    </button>
                    <button class="btn btn-secondary me-2" @click="poweroffSystem" style="border: none; color: #262626; font-size: 20px; width: 100px;">
                        Poweroff
                    </button>
                </div>
                <div class="btn-group me-2" style="width: 130px;">
                    <button class="btn btn-primary" style="border: none; background-color: rgb(179, 209, 255); color: #004085; font-size: 20px; width: 80px;" @click="automateFridge">
                        {{ automaticStrFridge }}
                    </button>
                    <button class="btn btn-primary" style="border: none; background-color: rgb(179, 209, 255); color: #004085; font-size: 20px; width: 50px;" @click="enableFridge">
                        {{ enabledStrFridge }}
                    </button>
                </div>
                <div>
                    <b-input-group size="sm" :style="{ width: '110px', marginRight: '8px' }">
                        <b-form-input id="fridgeSetpoint" v-model="controllerState.fridgeSetpoint" @focus="showNumpadForField('fridgeSetpoint')" class="form-control" :style="{ textAlign: 'center' , fontSize: '20px'}"></b-form-input>
                        <template #append>
                            <b-input-group-text :style="{ backgroundColor: 'rgb(179, 209, 255)', color: '#004085', borderRadius: '0 0.25rem 0.25rem 0', fontSize: '20px'}">&#176;F</b-input-group-text>
                        </template>
                    </b-input-group>
                </div>
                <div class="btn-group me-2" style="width: 130px">
                    <button class="btn btn-primary" style="border: none; background-color: rgb(255, 179, 179); color: #721c24; font-size: 20px; width: 80px;" @click="automateHeater">
                        {{ automaticStrHeater }}
                    </button>
                    <button class="btn btn-primary" style="border: none; background-color: rgb(255, 179, 179); color: #721c24; font-size: 20px; width: 50px;" @click="enableHeater">
                        {{ enabledStrHeater }}
                    </button>
                </div>
                <div>
                    <b-input-group size="sm" :style="{ width: '110px', marginRight: '8px' }">
                        <b-form-input id="heaterSetpoint" v-model="controllerState.heaterSetpoint" @focus="showNumpadForField('heaterSetpoint')" class="form-control" :style="{ textAlign: 'center', fontSize: '20px'}"></b-form-input>
                        <template #append>
                            <b-input-group-text :style="{ backgroundColor: 'rgba(255, 179, 179)', color: '#721c24', borderRadius: '0 0.25rem 0.25rem 0', fontSize: '20px'}">&#176;F</b-input-group-text>
                        </template>
                    </b-input-group>
                </div>
            </div>
            <div class="d-flex ms-auto" style="gap: 10px;">
                <button class="btn" :style="buttonStyle" @click="toggleFridgePower">
                    <i class="fas fa-snowflake" :style="fridgeButtonStyle"></i>
                </button>
                <button class="btn" :style="buttonStyle" @click="toggleHeaterPower">
                    <i class="fas fa-fire" :style="heaterButtonStyle"></i>
                </button>
            </div>
        </div>
    </div>
<div class="row align-items-center justify-content-center no-gutters mb-1">
    <div class="col-auto text-center">
        <div style="font-size: 12px; color: rgb(255, 205, 86); margin-bottom: -8px;">Gravity</div>
        <div style="font-size: 35px; font-weight: bold; color: rgb(255, 205, 86);">{{ formattedGravity }}</div>
    </div>
    <div class="col-auto text-center">
        <div style="font-size: 12px; color: rgb(34, 139, 34); margin-bottom: -8px;">ABV</div>
        <div style="font-size: 35px; font-weight: bold; color: rgb(34, 139, 34);">{{ formattedABV }}</div>
    </div>
    <div class="col-auto text-center">
        <div style="font-size: 12px; color: rgb(255, 159, 64); margin-bottom: -8px;">Atten</div>
        <div style="font-size: 35px; font-weight: bold; color: rgb(255, 159, 64);">{{ formattedAtten }}</div>
    </div>
    <div class="col-auto text-center">
        <div style="font-size: 12px; color: rgb(255, 102, 204); margin-bottom: -8px;">Beer Temp</div>
        <div style="font-size: 35px; font-weight: bold; color: rgb(255, 102, 204);">{{ formattedTemperature }}</div>
    </div>
    <div class="col-auto text-center">
        <div style="font-size: 12px; color: rgb(64, 224, 208); margin-bottom: -8px;">Fridge Temp</div>
        <div style="font-size: 35px; font-weight: bold; color: rgb(64, 224, 208);">{{ formattedW1Temperature }}</div>
    </div>
</div>
    <div class="row no-gutters mt-0">
        <div class="col-sm-6">
            <plot ref="chart1" :href="this.href + '/datahistory'" :timeRange="timeRange"></plot>
        </div>
        <div class="col-sm-6">
            <plot2 ref="chart2" :href="this.href + '/datahistory'" :timeRange="timeRange"></plot2>
        </div>
    </div>
    <div class="row no-gutters mt-0 justify-content-between align-items-center">
        <div class="col-auto">
            <select id="timeRange" @change="updateTimeRange" style="width: 100px; font-size: 10px;">
                <option value="30">Last 30 Minutes</option>
                <option value="60">Last 1 Hour</option>
                <option value="240" selected>Last 4 Hours</option>
                <option value="1440">Last 24 Hours</option>
                <option value="10080">Last 1 Week</option>
            </select>
        </div>
        <div class="col-auto text-end" style="font-size: 14px;">
            {{ formattedDateTime }}
        </div>
    </div>
    <!-- Numpad Component to be conditionally displayed -->
    <numpad ref="numpad" @update="handleNumpadUpdate"></numpad>
</div>
    `,
    data: function() {
        return {
            ws: null,
            controllerState: {
                fridgeSetpoint: 0, // Initialize with empty string
                heaterSetpoint: 0 // Initialize with empty strin
            },
            timeRange: 240,
            //showNumpad: false,
            activeField: '',
            formattedDateTime: moment().format('DD-MMM-YY hh:mma'),
            dateTimeInterval: null
        };
    },
    computed: {
        // Button formatting
        automaticStrFridge: function() {
            return this.controllerState.fridgeAutomatic ? "Auto" : "Manual";
        },
        automaticStrHeater: function() {
            return this.controllerState.heaterAutomatic ? "Auto" : "Manual";
        },
        enabledStrFridge: function() {
            return this.controllerState.fridgeEnabled ? "On" : "Off";
        },
        enabledStrHeater: function() {
            return this.controllerState.heaterEnabled ? "On" : "Off";
        },

        // Icon button formatting
        buttonStyle: function() {
            return {
                backgroundColor: 'transparent',
                borderColor: 'transparent',
                padding: '0.0rem',
                borderRadius: '50%'
            };
        },
        fridgeButtonStyle: function() {
            return {
                color: this.controllerState.fridgePower === 100 ? 'rgb(54, 162, 255)' : '#d3d3d3',
                fontSize: '36px'
            };
        },
        heaterButtonStyle: function() {
            return {
                color: this.controllerState.heaterPower === 100 ? 'rgb(255, 99, 132)' : '#d3d3d3',
                fontSize: '36px'
            };
        },

        // Unit formatting
        formattedABV: function() {
            if ('abv' in this.controllerState)
                return this.controllerState.abv.toFixed(2) + '%';
        },
        formattedAtten: function() {
            if ('atten' in this.controllerState)
                return this.controllerState.atten.toFixed(2) + '%';
        },
        //formattedDateTime: function() {
        //    return moment().format('DD-MMM-YY hh:mma');
        //},
        formattedGravity: function() {
            if ('specificGravity' in this.controllerState)
                return this.controllerState.specificGravity.toFixed(4) + ' SG';
        },
        formattedTemperature: function() {
            if ('temperature' in this.controllerState)
                return this.controllerState.temperature.toFixed(1)+'\u00B0F';
        },
        formattedW1Temperature: function() {
            if ('w1Temperature' in this.controllerState)
                return this.controllerState.w1Temperature.toFixed(1) + '\u00B0F';
        },
    },
    methods: {
        updateTimeRange(event) {
            this.timeRange = event.target.value;
        },
        newWsConn: function(url) {
            this.ws = new SockJS(url);
            this.ws.onmessage = msg => {
            console.log("Raw message data:", msg.data);
                // Directly map JSON data to desired camelCase properties in `controllerState`
                this.controllerState = {
                    temperature: msg.data.temperature,
                    w1Temperature: msg.data.w1temperature,
                    specificGravity: msg.data.gravity,
                    abv: msg.data.abv,
                    atten: msg.data.atten,
                    originalGravity: msg.data.ograv,
                    fridgeEnabled: msg.data.enabled,
                    fridgeAutomatic: msg.data.automatic,
                    fridgePower: msg.data.power,
                    fridgeSetpoint: msg.data.setpoint,
                    heaterEnabled: msg.data.heater_enabled,
                    heaterAutomatic: msg.data.heater_automatic,
                    heaterPower: msg.data.heater_power,
                    heaterSetpoint: msg.data.heater_setpoint,
                    wsUrl: msg.data.wsUrl
                };
                // Create a datapoint for charting
                const datapoint = {
                    'when': moment(),
                    'temperature': this.controllerState.temperature,
                    'w1Temperature': this.controllerState.w1Temperature,
                    'specificGravity': this.controllerState.specificGravity,
                    'abv': this.controllerState.abv,
                    'atten': this.controllerState.atten,
                    'originalGravity': this.controllerState.originalGravity,
                    'fridgePower': this.controllerState.fridgePower,
                    'fridgeSetpoint': this.controllerState.fridgeSetpoint,
                    'heaterPower': this.controllerState.heaterPower,
                    'heaterSetpoint': this.controllerState.heaterSetpoint
                };
                // Update charts with the new datapoint
                this.$refs.chart1.beerData(datapoint);
                this.$refs.chart2.tempData(datapoint);
            };
            this.ws.onclose = (e) => {
                console.log("Application WS Close", e);
                this.newWsConn(url);  // Reconnect WebSocket on close
            };
            this.ws.onerror = (e) => {
                console.log("Application WS Error: " + e);
            };
        },
        systemWsConn: function(url) {
            this.systemWs = new SockJS(url);
            this.systemWs.onmessage = msg => {
                console.log("System WebSocket message received: ", msg.data);
            };
            this.systemWs.onclose = (e) => {
                console.log("System WS Close", e);
                this.systemWsConn(url);
            };
            this.systemWs.onerror = (e) => {
                console.error("System WS Error: " + e);
            };
        },
        toggleFridgePower() {
            this.controllerState.fridgePower = this.controllerState.fridgePower === 100 ? 0 : 100;
            this.updateFridgePower(this.controllerState.fridgePower);
        },
        updateFridgePower: function(p) {
            this.ws.send(JSON.stringify({'controller': 'Fridge', 'power': p}));
        },
        enableFridge: function() {
            this.ws.send(JSON.stringify({'controller': 'Fridge', 'enabled': !this.controllerState.fridgeEnabled}));
        },
        automateFridge: function() {
            this.ws.send(JSON.stringify({'controller': 'Fridge', 'automatic': !this.controllerState.fridgeAutomatic}));
        },
        updateFridgeSetpoint: function(value) {
            this.controllerState.fridgeSetpoint = value;
            this.ws.send(JSON.stringify({'controller': 'Fridge', 'setpoint': value}));
        },
        toggleHeaterPower() {
            this.controllerState.heaterPower = this.controllerState.heaterPower === 100 ? 0 : 100;
            this.updateHeaterPower(this.controllerState.heaterPower);
        },
        updateHeaterPower: function(p) {
            this.ws.send(JSON.stringify({'controller': 'Heater', 'power': p}));
        },
        enableHeater: function() {
            this.ws.send(JSON.stringify({'controller': 'Heater', 'enabled': !this.controllerState.heaterEnabled}));
        },
        automateHeater: function() {
            this.ws.send(JSON.stringify({'controller': 'Heater', 'automatic': !this.controllerState.heaterAutomatic}));
        },
        updateHeaterSetpoint: function(value) {
            this.controllerState.heaterSetpoint = value;
            this.ws.send(JSON.stringify({'controller': 'Heater', 'setpoint': value}));
        },
        rebootSystem: function() {
            if (this.systemWs && this.systemWs.readyState === SockJS.OPEN) {
                console.log("Sending reboot command");
                this.systemWs.send("reboot");
            } else {
                console.error("System WebSocket is not open.");
            }
        },
        poweroffSystem: function() {
            if (this.systemWs && this.systemWs.readyState === SockJS.OPEN) {
                console.log("Sending poweroff command");
                this.systemWs.send("poweroff");
            } else {
                console.error("System WebSocket is not open.");
            }
        },
        showNumpadForField(field) {
            this.activeField = field;
            const value = this.controllerState[field] !== undefined ? this.controllerState[field].toString() : '0';
            this.$refs.numpad.showNumpad(field, value); // Pass the field name and value to the numpad
        },
        onNumpadEnter(value) {
            this.showNumpad = false;
            if (this.activeField === 'fridgeSetpoint') {
                this.controllerState.fridgeSetpoint = value;
                this.updateFridgeSetpoint(value);
            } else if (this.activeField === 'heaterSetpoint') {
                this.controllerState.heaterSetpoint = value;
                this.updateHeaterSetpoint(value);
            }
        },
        handleNumpadUpdate(value) {
            console.log("Numpad value received:", value);
            if (this.activeField) {
                this.controllerState[this.activeField] = parseFloat(value); // Ensure it's a float
                if (this.activeField === 'fridgeSetpoint') {
                    this.updateFridgeSetpoint(value);
                } else if (this.activeField === 'heaterSetpoint') {
                    this.updateHeaterSetpoint(value);
                }
            }
        }
    },
    mounted: function() {
        this.systemWsConn("http://192.168.254.53:8080/controllers/System/ws");
        fetch(this.href)
        .then(response => response.json())
        .then(json => {
            this.controllerState = json;
            this.newWsConn(this.controllerState.wsUrl);
        });
        this.dateTimeInterval = setInterval(() => {
            // Trigger Vue's reactivity system to refresh the computed property
            this.formattedDateTime = moment().format('DD-MMM-YY hh:mma');
        }, 1000);
    },
    beforeDestroy: function() {
        // Clear the interval when the component is destroyed to avoid memory leaks
        clearInterval(this.dateTimeInterval);
    }
});

var app = new Vue({
    el: '#app',
    data: {
        'rigs': {}
    },
    created: function() {
        fetch('/rigs')
        .then(response => response.json())
        .then(json => {
            this.rigs = json;
        });
    }
});

var darkModeStyles = document.createElement('style');
darkModeStyles.type = 'text/css';
darkModeStyles.innerHTML = `
  .dark-mode {
    background-color: #121212;
    color: #e0e0e0;
  }
  .dark-mode .b-button {
    background-color: #333;
    border-color: #555;
    color: #e0e0e0;
  }
  .dark-mode .b-form-input {
    background-color: #333;
    border-color: #555;
    color: #e0e0e0;
  }
  .dark-mode canvas {
    background-color: #333;
  }
  .dark-mode .chartjs-render-monitor {
    background-color: #1a1a1a;
  }
`;
document.head.appendChild(darkModeStyles);

