// filename: tfdeux2.js

// Main JavaScript for TFDeux visualization with ECharts and Vue.js

// Import global objects
const { createApp, ref, defineComponent } = Vue;
const { QBtn, QIcon } = Quasar;
const echarts = window.echarts;

// Global utility function for date formatting
const formatDate = (value) => {
    const date = new Date(value.value || value);
    const day = date.getDate().toString().padStart(2, '0');
    const month = date.toLocaleString('default', { month: 'short' }).toUpperCase();
    const year = date.getFullYear().toString().slice(-2);
    const hours = date.getHours() % 12 || 12;
    const minutes = date.getMinutes().toString().padStart(2, '0');
    const ampm = date.getHours() >= 12 ? 'PM' : 'AM';
    return `${day}${month}${year} ${hours}:${minutes} ${ampm}`;
};

const getInitialTemperatureUnit = () => {
    const params = new URLSearchParams(window.location.search);
    const unitFromUrl = params.get('unit');
    if (unitFromUrl === 'F' || unitFromUrl === 'C') {
        return unitFromUrl;
    }

    const unitFromStorage = localStorage.getItem('tfdeuxTemperatureUnit');
    if (unitFromStorage === 'F' || unitFromStorage === 'C') {
        return unitFromStorage;
    }

    return 'F';
};

const formatTemperatureValue = (fahrenheitValue, unit) => {
    const f = Number(fahrenheitValue);
    const c = ((f - 32) * 5) / 9;
    return unit === 'C' ? `${c.toFixed(1)}°C` : `${f.toFixed(1)}°F`;
};

// Utility function to create chart options
const createChartOptions = (legendData, seriesData, yAxisOptions, getTemperatureUnit) => ({
    tooltip: {
        trigger: 'axis',
        axisPointer: {
            type: 'line',
            label: { show: true, formatter: formatDate },
        },
        formatter: function (params) {
            if (!params || !params.length) {
                return '';
            }

            const currentUnit = getTemperatureUnit();
            let result = `${formatDate(params[0].axisValue)}<br/>`;

            params.forEach(item => {
                const value = item.value[1];

                if (item.seriesName.includes('Temp') || item.seriesName.includes('Setpoint')) {
                    result += `${item.marker} ${item.seriesName} ${formatTemperatureValue(value, currentUnit)}<br/>`;
                } else if (item.seriesName.includes('Power')) {
                    const powerValue = Number(value);
                    const powerText = powerValue === 100 ? 'On' : powerValue === 0 ? 'Off' : powerValue;
                    result += `${item.marker} ${item.seriesName} ${powerText}<br/>`;
                } else {
                    result += `${item.marker} ${item.seriesName} ${value}<br/>`;
                }
            });

            return result;
        },
    },
    legend: {
        data: legendData,
        textStyle: {
            color: '#d9dde3',
        },
        inactiveColor: '#7f8791',
    },
    xAxis: {
        type: 'time',
        boundaryGap: false,
        axisLabel: {
            formatter: formatDate,
            rotate: 30,
            align: 'right',
        },
        splitNumber: 10,
        min: 'dataMin',
        max: 'dataMax',
    },
    yAxis: yAxisOptions.map((axis, index) => ({
        ...axis,
        splitLine: { show: false },
        offset: index > 1 ? (index - 1) * 30 : 0,
    })),
    series: seriesData,
    dataZoom: [
        {
            type: 'inside',
        },
    ],
});

// FermentationPlotComponent for fermentation-specific charts
const FermentationPlotComponent = defineComponent({
    name: 'FermentationPlotComponent',
    props: {
        fridgeData: { type: Object, required: true },
        temperatureUnit: { type: String, required: true },
    },
    setup(props) {
        const chartRef = ref(null);

        const initializeChart = () => {
            const chartInstance = echarts.init(chartRef.value);
            chartInstance.group = 'sharedTimeline';

            const options = createChartOptions(
                ['Gravity', 'OG', 'ABV', 'Attenuation'],
                [
                    { name: 'Gravity', type: 'line', smooth: true, data: [], showSymbol: false, yAxisIndex: 0 },
                    { name: 'OG', type: 'line', smooth: true, data: [], showSymbol: false, yAxisIndex: 0 },
                    { name: 'ABV', type: 'line', smooth: true, data: [], showSymbol: false, yAxisIndex: 1 },
                    { name: 'Attenuation', type: 'line', smooth: true, data: [], showSymbol: false, yAxisIndex: 2 },
                ],
                [
                    { name: 'Gravity', type: 'value', min: 0, max: 1.25 },
                    { name: 'ABV', type: 'value', min: 0, max: 20 },
                    { name: 'Atten', type: 'value', min: 0, max: 100 },
                ],
                () => props.temperatureUnit
            );

            const timestamps = props.fridgeData.label.map(ts => ts * 1000);
            options.series[0].data = timestamps.map((time, i) => [time, props.fridgeData.gravity[i]]);
            options.series[1].data = timestamps.map((time, i) => [time, props.fridgeData.ograv[i]]);
            options.series[2].data = timestamps.map((time, i) => [time, props.fridgeData.abv[i]]);
            options.series[3].data = timestamps.map((time, i) => [time, props.fridgeData.atten[i]]);

            chartInstance.setOption(options);
        };

        return { chartRef, initializeChart };
    },
    mounted() {
        this.initializeChart();
    },
    template: `<div ref="chartRef" class="chart" style="width: 100%; height: 400px;"></div>`,
});

// TemperaturePlotComponent for temperature-specific charts
const TemperaturePlotComponent = defineComponent({
    name: 'TemperaturePlotComponent',
    props: {
        fridgeData: { type: Object, required: true },
        heaterData: { type: Object, required: true },
        temperatureUnit: { type: String, required: true },
    },
    setup(props) {
        const chartRef = ref(null);

        const initializeChart = () => {
            const chartInstance = echarts.init(chartRef.value);
            chartInstance.group = 'sharedTimeline';

            const options = createChartOptions(
                ['Beer Temp', 'Fridge Temp', 'Cold Setpoint', 'Hot Setpoint', 'Cold Power', 'Hot Power'],
                [
                    { name: 'Beer Temp', type: 'line', smooth: true, data: [], showSymbol: false, yAxisIndex: 0 },
                    { name: 'Fridge Temp', type: 'line', smooth: true, data: [], showSymbol: false, yAxisIndex: 0 },
                    { name: 'Cold Setpoint', type: 'line', smooth: true, data: [], showSymbol: false, yAxisIndex: 0 },
                    { name: 'Hot Setpoint', type: 'line', smooth: true, data: [], showSymbol: false, yAxisIndex: 0 },
                    { name: 'Cold Power', type: 'line', smooth: true, data: [], showSymbol: false, yAxisIndex: 1 },
                    { name: 'Hot Power', type: 'line', smooth: true, data: [], showSymbol: false, yAxisIndex: 1 },
                ],
                [
                    { name: 'Temperature', type: 'value', min: 30, max: 120 },
                    {
                        name: 'Power',
                        type: 'value',
                        min: 0,
                        max: 100,
                        axisLabel: {
                            formatter: value => (value === 0 ? 'Off' : value === 100 ? 'On' : ''),
                        },
                    },
                ],
                () => props.temperatureUnit
            );

            options.legend.data = ['Beer Temp', 'Fridge Temp', 'Cold Setpoint', 'Hot Setpoint', 'Cold Power', 'Hot Power'];
            options.legend.selected = {
                'Cold Power': false,
                'Hot Power': false,
            };

            const timestamps = props.fridgeData.label.map(ts => ts * 1000);
            options.series[0].data = timestamps.map((time, i) => [time, props.fridgeData.temperature[i]]);
            options.series[1].data = timestamps.map((time, i) => [time, props.fridgeData.fridgeTemperature[i]]);
            options.series[2].data = timestamps.map((time, i) => [time, props.fridgeData.setpoint[i]]);
            options.series[3].data = timestamps.map((time, i) => [time, props.heaterData.setpoint[i]]);
            options.series[4].data = timestamps.map((time, i) => [time, props.fridgeData.power[i]]);
            options.series[5].data = timestamps.map((time, i) => [time, props.heaterData.power[i]]);

            chartInstance.setOption(options);
        };

        return { chartRef, initializeChart };
    },
    mounted() {
        this.initializeChart();
    },
    template: `<div ref="chartRef" class="chart" style="width: 100%; height: 400px;"></div>`,
});

// Main Vue app
createApp({
    components: { FermentationPlotComponent, TemperaturePlotComponent },
    template: `
        <div>
            <div class="header-info">
                <div>TFDeux</div>
                <div class="header-item">
                    OG: {{ originalGravity !== null ? originalGravity.toFixed(4) : 'Loading...' }}
                </div>
                <div class="header-item">{{ formattedDateTime }}</div>
                <div class="header-buttons">
                    <q-btn
                        flat
                        @click="toggleTemperatureUnit"
                        :label="'Units: °' + temperatureUnit" />
                    <q-btn flat @click="reloadPage" icon="refresh" />
                    <q-btn flat @click="closeTab" icon="close" />
                </div>
            </div>
            <div v-if="fridgeData && heaterData" class="chart-container">
                <fermentation-plot-component
                    :fridge-data="fridgeData"
                    :temperature-unit="temperatureUnit">
                </fermentation-plot-component>

                <temperature-plot-component
                    :fridge-data="fridgeData"
                    :heater-data="heaterData"
                    :temperature-unit="temperatureUnit">
                </temperature-plot-component>
            </div>
        </div>
    `,
    setup() {
        const fridgeData = ref(null);
        const heaterData = ref(null);
        const originalGravity = ref(null);
        const formattedDateTime = ref(new Date().toLocaleString());
        const temperatureUnit = ref(getInitialTemperatureUnit());

        const fetchDataUrls = async () => {
            try {
                const response = await fetch('/controllers');
                if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
                const data = await response.json();

                if (data.Fridge) {
                    const fridgeResponse = await fetch(`${data.Fridge.url}/datahistory`);
                    const fridgeResult = await fridgeResponse.json();
                    fridgeData.value = fridgeResult;
                    originalGravity.value = fridgeResult.ograv?.[fridgeResult.ograv.length - 1] || null;
                }

                if (data.Heater) {
                    const heaterResponse = await fetch(`${data.Heater.url}/datahistory`);
                    heaterData.value = await heaterResponse.json();
                }
            } catch (error) {
                console.error('Error fetching data URLs:', error);
            }
        };

        const toggleTemperatureUnit = () => {
            temperatureUnit.value = temperatureUnit.value === 'F' ? 'C' : 'F';
            localStorage.setItem('tfdeuxTemperatureUnit', temperatureUnit.value);

            const url = new URL(window.location.href);
            url.searchParams.set('unit', temperatureUnit.value);
            window.history.replaceState({}, '', url);
        };

        const reloadPage = () => window.location.reload();
        const closeTab = () => window.close();

        setInterval(() => {
            formattedDateTime.value = new Date().toLocaleString();
        }, 1000);

        return {
            fridgeData,
            heaterData,
            originalGravity,
            formattedDateTime,
            temperatureUnit,
            fetchDataUrls,
            toggleTemperatureUnit,
            reloadPage,
            closeTab,
        };
    },
    mounted() {
        this.fetchDataUrls();

        this.$nextTick(() => {
            echarts.connect('sharedTimeline');
        });
    },
})
.use(Quasar)
.mount('#app');
