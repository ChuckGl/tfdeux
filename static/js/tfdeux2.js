// filename: tfdeux2.js

// Main JavaScript for TFDeux visualization with ECharts and Vue.js

// Import global objects
const { createApp, ref, defineComponent } = Vue;
const { QBtn, QIcon } = Quasar;
const echarts = window.echarts;

// Global utility function for date formatting
const formatDate = (value) => {
    const date = new Date(value.value || value); // Handle both axisPointer and axisLabel cases
    const day = date.getDate().toString().padStart(2, '0');
    const month = date.toLocaleString('default', { month: 'short' }).toUpperCase();
    const year = date.getFullYear().toString().slice(-2);
    const hours = date.getHours() % 12 || 12;
    const minutes = date.getMinutes().toString().padStart(2, '0');
    const ampm = date.getHours() >= 12 ? 'PM' : 'AM';
    return `${day}${month}${year} ${hours}:${minutes} ${ampm}`;
};

// Utility function to create chart options
const createChartOptions = (legendData, seriesData, yAxisOptions) => ({
    tooltip: {
        trigger: 'axis',
        axisPointer: {
            type: 'line',
            label: { show: true, formatter: formatDate },
        },
    },
    legend: { data: legendData },
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
        splitLine: { show: false, },
        offset: index > 1 ? (index - 1) * 30 : 0, // Start offset after second axis
    })),
    series: seriesData,
});

// FermentationPlotComponent for fermentation-specific charts
const FermentationPlotComponent = defineComponent({
    name: 'FermentationPlotComponent',
    props: {
        fridgeData: { type: Object, required: true }, // Use fridge data directly
    },
    setup(props) {
        const chartRef = ref(null);

        const initializeChart = () => {
            const chartInstance = echarts.init(chartRef.value);
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
                ]
            );

            // Map data to series
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
        fridgeData: { type: Object, required: true }, // Use fridge data directly
        heaterData: { type: Object, required: true }, // Use heater data directly
    },
    setup(props) {
        const chartRef = ref(null);

        const initializeChart = () => {
            const chartInstance = echarts.init(chartRef.value);
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
                            formatter: function (value) {
                                if (value === 0) return 'Off';
                                if (value === 100) return 'On';
                                return '';
                            },
                        },
                    },
                ]
            );

            options.legend = {
                data: ['Beer Temp', 'Fridge Temp', 'Cold Setpoint', 'Hot Setpoint', 'Cold Power', 'Hot Power'],
                selected: {
                    'Cold Power': false, // Disabled by default
                    'Hot Power': false,  // Disabled by default
                },
            };

            // Map data to series
            const timestamps = props.fridgeData.label.map(ts => ts * 1000);
            options.series[0].data = timestamps.map((time, i) => [time, props.fridgeData.temperature[i]]);
            options.series[1].data = timestamps.map((time, i) => [time, props.fridgeData.w1temperature[i]]);
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
                    <q-btn flat @click="reloadPage" icon="refresh" />
                    <q-btn flat @click="closeTab" icon="close" />
                </div>
            </div>
            <div v-if="fridgeData && heaterData" class="chart-container">
                <fermentation-plot-component :fridge-data="fridgeData"></fermentation-plot-component>
                <temperature-plot-component
                    :fridge-data="fridgeData"
                    :heater-data="heaterData">
                </temperature-plot-component>
            </div>
        </div>
    `,
    setup() {
        const fridgeData = ref(null);
        const heaterData = ref(null);
        const originalGravity = ref(null);
        const formattedDateTime = ref(new Date().toLocaleString());

        const fetchDataUrls = async () => {
            try {
                const response = await fetch('/controllers');
                if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
                const data = await response.json();

                if (data.Fridge) {
                    const fridgeResponse = await fetch(`${data.Fridge.url}/datahistory`);
                    const fridgeResult = await fridgeResponse.json();
                    fridgeData.value = fridgeResult;
                    originalGravity.value = fridgeResult.ograv?.[0] || null;
                }

                if (data.Heater) {
                    const heaterResponse = await fetch(`${data.Heater.url}/datahistory`);
                    heaterData.value = await heaterResponse.json();
                }
            } catch (error) {
                console.error('Error fetching data URLs:', error);
            }
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
            fetchDataUrls,
            reloadPage,
            closeTab,
        };
    },
    mounted() {
        this.fetchDataUrls();
    },
})
.use(Quasar)
.mount('#app');

