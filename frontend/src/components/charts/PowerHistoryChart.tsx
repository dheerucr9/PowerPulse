import { useEffect, useMemo, useRef } from "react";
import * as echarts from "echarts";

import { BarHistoryInterval, HistoryChartData, HistoryChartType } from "@/api/models";
import { chartPalette } from "@/features/live/live-utils";

function hexToRgba(color: string, alpha: number) {
  const normalized = color.trim().replace("#", "");
  const hex = normalized.length === 3
    ? normalized
        .split("")
        .map((part) => `${part}${part}`)
        .join("")
    : normalized;

  if (!/^[0-9a-fA-F]{6}$/.test(hex)) {
    return color;
  }

  const value = Number.parseInt(hex, 16);
  const red = (value >> 16) & 255;
  const green = (value >> 8) & 255;
  const blue = value & 255;

  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

function formatBucketLabel(timestamp: number, interval: BarHistoryInterval) {
  const date = new Date(timestamp * 1000);

  if (interval === "day") {
    return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(date);
  }

  if (interval === "week") {
    return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(date);
  }

  return new Intl.DateTimeFormat(undefined, { month: "short", year: "2-digit" }).format(date);
}

function formatBucketTooltipTitle(timestamp: number, interval: BarHistoryInterval) {
  const date = new Date(timestamp * 1000);

  if (interval === "day") {
    return new Intl.DateTimeFormat(undefined, { weekday: "short", month: "long", day: "numeric" }).format(date);
  }

  if (interval === "week") {
    return `Week of ${new Intl.DateTimeFormat(undefined, { month: "long", day: "numeric", year: "numeric" }).format(date)}`;
  }

  return new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" }).format(date);
}

interface PowerHistoryChartProps {
  data: HistoryChartData | null;
  panelLabel: string;
  chartType: HistoryChartType;
  barInterval: BarHistoryInterval;
  className?: string;
  testId?: string;
}

export function PowerHistoryChart({
  data,
  panelLabel,
  chartType,
  barInterval,
  className = "",
  testId
}: PowerHistoryChartProps) {
  const elementRef = useRef<HTMLDivElement | null>(null);
  const barAxisData = useMemo(() => {
    if (!data) {
      return [];
    }

    const timestamps = new Set<number>();

    [data.production, data.consumption, data.charger, data.net].forEach((series) => {
      if (series) {
        series.forEach((point) => {
          timestamps.add(point.ts);
        });
      }
    });

    return [...timestamps].sort((left, right) => left - right);
  }, [data]);

  useEffect(() => {
    if (!elementRef.current) {
      return undefined;
    }

    const chart = echarts.init(elementRef.current, undefined, { renderer: "canvas" });
    const handleResize = () => chart.resize();
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.dispose();
    };
  }, []);

  useEffect(() => {
    if (!elementRef.current) {
      return;
    }

    const chart = echarts.getInstanceByDom(elementRef.current);

    if (!chart) {
      return;
    }

    if (!data) {
      chart.clear();
      return;
    }

    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    const rootStyles = getComputedStyle(document.documentElement);
    const textColor = rootStyles.getPropertyValue("--color-text").trim() || (isDark ? "#f5f5f7" : "#1c1c1e");
    const mutedStrong = rootStyles.getPropertyValue("--color-text-secondary").trim() || (isDark ? "#98989d" : "#6b6b6b");
    const textSubtle = rootStyles.getPropertyValue("--color-text-tertiary").trim() || (isDark ? "#6e6e73" : "#a3a3a3");
    const borderSubtle = rootStyles.getPropertyValue("--color-border-subtle").trim() || (isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(28, 28, 30, 0.08)");
    const borderMedium = rootStyles.getPropertyValue("--color-border-medium").trim() || (isDark ? "rgba(255, 255, 255, 0.14)" : "rgba(28, 28, 30, 0.14)");
    const surface = rootStyles.getPropertyValue("--color-surface").trim() || (isDark ? "#2c2c2e" : "#ffffff");
    const surfaceAlt = rootStyles.getPropertyValue("--color-surface-alt").trim() || (isDark ? "#3c3c3e" : "#f5f4f0");
    const fontUi = rootStyles.getPropertyValue("--font-ui").trim() || "sans-serif";
    const warningColor = rootStyles.getPropertyValue("--color-warning").trim() || "#B8860B";
    const infoColor = rootStyles.getPropertyValue("--color-info").trim() || "#4A6FA5";
    const chargerColor = rootStyles.getPropertyValue("--color-charger").trim() || chartPalette.charger;

    const makeLineSeries = (
      points: HistoryChartData[keyof HistoryChartData],
      name: string,
      color: string
    ) => {
      if (!points.length) {
        return null;
      }

      return {
        name,
        type: "line",
        data: points.map((point) => [point.ts * 1000, point.val]),
        showSymbol: false,
        smooth: true,
        universalTransition: true,
        lineStyle: {
          width: 2.5,
          color,
          shadowBlur: 8,
          shadowColor: hexToRgba(color, 0.16)
        },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: hexToRgba(color, 0.2) },
              { offset: 0.68, color: hexToRgba(color, 0.06) },
              { offset: 1, color: hexToRgba(color, 0.01) }
            ]
          }
        },
        sampling: "lttb",
        emphasis: { focus: "series" },
        progressive: 4000,
        progressiveThreshold: 12000
      };
    };

    const lineSeries = [
      makeLineSeries(data.production, "Production", chartPalette.production),
      makeLineSeries(data.consumption, "Consumption", chartPalette.consumption),
      makeLineSeries(data.net, "Net", chartPalette.net),
      makeLineSeries(data.panel, `Panel (${panelLabel || "Panel"})`, chartPalette.panel),
      makeLineSeries(data.charger, "Charger", chartPalette.charger)
    ].filter(Boolean) as echarts.SeriesOption[];

    const makeStackedBarSeries = (
      points: HistoryChartData[keyof HistoryChartData],
      name: string,
      color: string,
      stackId?: string,
      invert?: boolean
    ) => {
      if (!points.length || !barAxisData.length) {
        return null;
      }

      const valuesByTimestamp = new Map(points.map((point) => [point.ts, point.val]));

      return {
        name,
        type: "bar",
        stack: stackId,
        data: barAxisData.map((timestamp) => {
          const val = Number(valuesByTimestamp.get(timestamp) ?? 0);
          return invert ? -val : val;
        }),
        barMaxWidth: 36,
        barGap: "30%",
        universalTransition: true,
        itemStyle: {
          color,
          borderRadius: invert ? [0, 0, 4, 4] : [4, 4, 0, 0],
          shadowBlur: 6,
          shadowColor: hexToRgba(color, 0.12)
        },
        emphasis: {
          focus: "series",
          itemStyle: {
            color: hexToRgba(color, 0.9)
          }
        }
      };
    };

    const makeNetLineSeries = () => {
      if (!data.net?.length || !barAxisData.length) {
        return null;
      }

      const valuesByTimestamp = new Map(data.net.map((point) => [point.ts, point.val]));
      // For category x-axis (bar chart), use indices instead of timestamps
      const lineData = barAxisData.map((timestamp, index) => {
        const val = Number(valuesByTimestamp.get(timestamp) ?? null);
        return [index, val];
      }).filter(([, val]) => val !== null && !isNaN(val));
      
      if (lineData.length === 0) {
        return null;
      }

      return {
        name: "Net",
        type: "line",
        data: lineData,
        showSymbol: false,
        smooth: false,
        lineStyle: {
          width: 2.5,
          color: chartPalette.net,
          type: "dashed"
        },
        emphasis: {
          focus: "series"
        },
        yAxisIndex: 0
      };
    };

    const barSeries = [
      makeStackedBarSeries(data.production, "Production", warningColor, "energy"),
      makeStackedBarSeries(data.consumption, "Consumption", infoColor, "energy", true),
      makeStackedBarSeries(data.charger, "Charger", chargerColor, "energy", true),
      makeNetLineSeries()
    ].filter(Boolean) as echarts.SeriesOption[];

    const isBarChart = chartType === "bar";
    const barLabels = barAxisData.map((timestamp) => formatBucketLabel(timestamp, barInterval));
    const option = {
      backgroundColor: "transparent",
      color: isBarChart
        ? [warningColor, infoColor, chargerColor, chartPalette.net]
        : [chartPalette.production, chartPalette.consumption, chartPalette.net, chartPalette.panel, chartPalette.charger],
      textStyle: {
        fontFamily: fontUi
      },
      animationDuration: 450,
      animationDurationUpdate: 450,
      animationEasing: "cubicOut",
      animationEasingUpdate: "cubicOut",
      tooltip: {
        trigger: "axis",
        confine: true,
        backgroundColor: hexToRgba(surface, 0.98),
        borderColor: borderMedium,
        borderWidth: 1,
        padding: [10, 12],
        textStyle: {
          color: textColor,
          fontFamily: fontUi,
          fontSize: 12,
          lineHeight: 18
        },
        extraCssText: "border-radius: 12px; box-shadow: var(--shadow-card);",
        axisPointer: isBarChart
          ? {
              type: "shadow",
              shadowStyle: {
                color: hexToRgba(infoColor, 0.08)
              }
            }
          : {
              type: "cross",
              lineStyle: {
                color: borderMedium,
                type: "dashed"
              },
              label: {
                backgroundColor: surfaceAlt,
                color: textColor,
                borderColor: borderMedium,
                borderWidth: 1
              }
            },
        formatter: (params: unknown) => {
          const points = Array.isArray(params) ? params : [params];
          const seen = new Set<string>();
          const rows: string[] = [];

          const axisValue = isBarChart
            ? formatBucketTooltipTitle(barAxisData[(points[0] as { dataIndex?: number } | undefined)?.dataIndex ?? 0] ?? 0, barInterval)
            : (points[0] as { axisValueLabel?: string } | undefined)?.axisValueLabel ?? "";

          for (const point of points as Array<{
            seriesName?: string;
            marker?: string;
            value?: number | [number, number];
          }>) {
            if (!point.seriesName || seen.has(point.seriesName)) {
              continue;
            }

            seen.add(point.seriesName);
            const rawValue = Array.isArray(point.value) ? point.value[1] : point.value;
            const numericValue = Number(rawValue);

            if (!Number.isFinite(numericValue)) {
              continue;
            }

            rows.push(`${point.marker ?? ""}${point.seriesName}: ${numericValue.toFixed(2)} ${isBarChart ? "kWh" : "kW"}`);
          }

          return [axisValue, ...rows].join("<br/>");
        }
      },
      legend: { 
        show: true,
        bottom: 0,
        textStyle: { color: mutedStrong, fontSize: 11 }
      },
      grid: isBarChart
        ? { left: 58, right: 18, top: 26, bottom: 44 }
        : { left: 58, right: 18, top: 26, bottom: 72 },
      toolbox: {
        right: 10,
        iconStyle: {
          borderColor: mutedStrong
        },
        emphasis: {
          iconStyle: {
            borderColor: textColor
          }
        },
        feature: { saveAsImage: { pixelRatio: 2 } }
      },
      dataZoom: isBarChart
        ? []
        : [
            { type: "inside", filterMode: "none" },
            {
              type: "slider",
              height: 22,
              bottom: 18,
              borderColor: borderSubtle,
              backgroundColor: hexToRgba(surfaceAlt, 0.92),
              fillerColor: hexToRgba(chartPalette.net, 0.14),
              handleStyle: {
                color: surface,
                borderColor: borderMedium
              },
              moveHandleStyle: {
                color: textSubtle,
                opacity: 0.8
              },
              textStyle: {
                color: mutedStrong
              }
            }
          ],
      xAxis: isBarChart
        ? {
            type: "category",
            data: barLabels,
            boundaryGap: true,
            axisLabel: {
              color: mutedStrong,
              margin: 14
            },
            axisLine: { lineStyle: { color: borderMedium } },
            axisTick: { show: false },
            splitLine: { show: false },
            name: barInterval === "month" ? "Month" : barInterval === "week" ? "Week" : "Day",
            nameGap: 30,
            nameTextStyle: { color: mutedStrong, fontWeight: 700 }
          }
        : {
            type: "time",
            boundaryGap: false,
            axisLabel: { color: mutedStrong, margin: 14 },
            axisLine: { lineStyle: { color: borderMedium } },
            axisTick: { show: false },
            splitLine: {
              lineStyle: {
                color: borderSubtle,
                type: "dashed"
              }
            },
            name: "Time",
            nameGap: 30,
            nameTextStyle: { color: mutedStrong, fontWeight: 700 }
          },
      yAxis: {
        type: "value",
        scale: true,
        axisLabel: {
          color: mutedStrong,
          formatter: (value: number) => {
            return `${value.toFixed(0)}`;
          }
        },
        axisLine: { show: false },
        splitLine: {
          lineStyle: {
            color: borderSubtle,
            type: "dashed"
          }
        },
        name: isBarChart ? "Energy (kWh)" : "Power (kW)",
        nameGap: 28,
        nameTextStyle: { color: mutedStrong, fontWeight: 700 }
      },
      series: isBarChart ? barSeries : lineSeries
    };

    chart.setOption(option as echarts.EChartsOption, { notMerge: true, lazyUpdate: true });
  }, [barAxisData, barInterval, chartType, data, panelLabel]);

  return <div ref={elementRef} className={className} data-testid={testId} />;
}
