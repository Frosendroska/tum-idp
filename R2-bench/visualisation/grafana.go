package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

// GrafanaDashboard represents a Grafana dashboard configuration
type GrafanaDashboard struct {
	Dashboard DashboardConfig `json:"dashboard"`
	FolderID  int             `json:"folderId"`
	Overwrite bool            `json:"overwrite"`
}

// DashboardConfig represents the dashboard configuration
type DashboardConfig struct {
	ID          interface{} `json:"id"`
	Title       string      `json:"title"`
	Tags        []string    `json:"tags"`
	Style       string      `json:"style"`
	Timezone    string      `json:"timezone"`
	Panels      []Panel     `json:"panels"`
	Time        TimeRange   `json:"time"`
	Timepicker  Timepicker  `json:"timepicker"`
	Templating  Templating  `json:"templating"`
	Annotations Annotations `json:"annotations"`
	Refresh     string      `json:"refresh"`
	SchemaVersion int       `json:"schemaVersion"`
	Version     int         `json:"version"`
	Links       []Link      `json:"links"`
}

// Panel represents a Grafana panel
type Panel struct {
	ID          int         `json:"id"`
	Title       string      `json:"title"`
	Type        string      `json:"type"`
	GridPos     GridPos     `json:"gridPos"`
	Targets     []Target    `json:"targets"`
	FieldConfig FieldConfig `json:"fieldConfig"`
	Options     interface{} `json:"options,omitempty"`
}

// GridPos represents panel grid position
type GridPos struct {
	H int `json:"h"`
	W int `json:"w"`
	X int `json:"x"`
	Y int `json:"y"`
}

// Target represents a query target
type Target struct {
	Expr         string `json:"expr"`
	LegendFormat string `json:"legendFormat,omitempty"`
	RefID        string `json:"refId"`
}

// FieldConfig represents field configuration
type FieldConfig struct {
	Defaults Defaults `json:"defaults"`
}

// Defaults represents default field settings
type Defaults struct {
	Color       Color  `json:"color"`
	Custom      Custom `json:"custom"`
	Mappings    []interface{} `json:"mappings"`
	Thresholds  Thresholds    `json:"thresholds"`
	Unit        string        `json:"unit"`
}

// Color represents color configuration
type Color struct {
	Mode string `json:"mode"`
}

// Custom represents custom field configuration
type Custom struct {
	AxisLabel     string `json:"axisLabel"`
	AxisPlacement string `json:"axisPlacement"`
	BarAlignment  int    `json:"barAlignment"`
	DrawStyle     string `json:"drawStyle"`
	FillOpacity   int    `json:"fillOpacity"`
	GradientMode  string `json:"gradientMode"`
	HideFrom      HideFrom `json:"hideFrom"`
	LineInterpolation string `json:"lineInterpolation"`
	LineWidth     int    `json:"lineWidth"`
	PointSize     int    `json:"pointSize"`
	ScaleDistribution ScaleDistribution `json:"scaleDistribution"`
	ShowPoints    string `json:"showPoints"`
	SpanNulls     bool   `json:"spanNulls"`
	Stacking      Stacking `json:"stacking"`
	ThresholdsStyle ThresholdsStyle `json:"thresholdsStyle"`
}

// HideFrom represents hide configuration
type HideFrom struct {
	Legend  bool `json:"legend"`
	Tooltip bool `json:"tooltip"`
	Viz     bool `json:"viz"`
}

// ScaleDistribution represents scale distribution
type ScaleDistribution struct {
	Type string `json:"type"`
}

// Stacking represents stacking configuration
type Stacking struct {
	Group string `json:"group"`
	Mode  string `json:"mode"`
}

// ThresholdsStyle represents thresholds style
type ThresholdsStyle struct {
	Mode string `json:"mode"`
}

// Thresholds represents thresholds configuration
type Thresholds struct {
	Mode  string        `json:"mode"`
	Steps []ThresholdStep `json:"steps"`
}

// ThresholdStep represents a threshold step
type ThresholdStep struct {
	Color string  `json:"color"`
	Value float64 `json:"value"`
}

// TimeRange represents time range
type TimeRange struct {
	From string `json:"from"`
	To   string `json:"to"`
}

// Timepicker represents timepicker configuration
type Timepicker struct {
	RefreshIntervals []string `json:"refresh_intervals"`
}

// Templating represents templating configuration
type Templating struct {
	List []interface{} `json:"list"`
}

// Annotations represents annotations configuration
type Annotations struct {
	List []interface{} `json:"list"`
}

// Link represents a dashboard link
type Link struct {
	AsDropdown  bool   `json:"asDropdown"`
	Icon        string `json:"icon"`
	IncludeVars bool   `json:"includeVars"`
	Tags        []string `json:"tags"`
	TargetBlank bool   `json:"targetBlank"`
	Title       string `json:"title"`
	Tooltip     string `json:"tooltip"`
	Type        string `json:"type"`
	URL         string `json:"url"`
}

// CreateR2BenchmarkDashboard creates a Grafana dashboard for R2 benchmarking
func CreateR2BenchmarkDashboard() *GrafanaDashboard {
	return &GrafanaDashboard{
		Dashboard: DashboardConfig{
			ID:          nil,
			Title:       "R2 Benchmark Dashboard",
			Tags:        []string{"r2", "benchmark", "performance"},
			Style:       "dark",
			Timezone:    "browser",
			SchemaVersion: 30,
			Version:     1,
			Refresh:     "10s",
			Time: TimeRange{
				From: "now-1h",
				To:   "now",
			},
			Timepicker: Timepicker{
				RefreshIntervals: []string{"5s", "10s", "30s", "1m", "5m", "15m", "30m", "1h", "2h", "1d"},
			},
			Templating:  Templating{List: []interface{}{}},
			Annotations: Annotations{List: []interface{}{}},
			Links:       []Link{},
			Panels: []Panel{
				// Throughput Panel
				{
					ID:    1,
					Title: "Throughput (Mbps)",
					Type:  "timeseries",
					GridPos: GridPos{
						H: 8,
						W: 12,
						X: 0,
						Y: 0,
					},
					Targets: []Target{
						{
							Expr:         `r2_bench_throughput_mbps`,
							LegendFormat: "{{instance_type}} - C{{concurrency}}",
							RefID:        "A",
						},
					},
					FieldConfig: FieldConfig{
						Defaults: Defaults{
							Color: Color{Mode: "palette-classic"},
							Custom: Custom{
								AxisLabel:     "",
								AxisPlacement: "auto",
								BarAlignment:  0,
								DrawStyle:     "line",
								FillOpacity:   10,
								GradientMode:  "none",
								HideFrom:      HideFrom{Legend: false, Tooltip: false, Viz: false},
								LineInterpolation: "linear",
								LineWidth:     1,
								PointSize:     5,
								ScaleDistribution: ScaleDistribution{Type: "linear"},
								ShowPoints:    "never",
								SpanNulls:     false,
								Stacking:      Stacking{Group: "A", Mode: "none"},
								ThresholdsStyle: ThresholdsStyle{Mode: "off"},
							},
							Mappings: []interface{}{},
							Thresholds: Thresholds{
								Mode: "absolute",
								Steps: []ThresholdStep{
									{Color: "green", Value: 0},
									{Color: "red", Value: 80},
								},
							},
							Unit: "Mbps",
						},
					},
				},
				// Latency Panel
				{
					ID:    2,
					Title: "Latency (ms)",
					Type:  "timeseries",
					GridPos: GridPos{
						H: 8,
						W: 12,
						X: 12,
						Y: 0,
					},
					Targets: []Target{
						{
							Expr:         `histogram_quantile(0.50, rate(r2_bench_latency_ms_bucket[5m]))`,
							LegendFormat: "P50 - {{instance_type}}",
							RefID:        "A",
						},
						{
							Expr:         `histogram_quantile(0.90, rate(r2_bench_latency_ms_bucket[5m]))`,
							LegendFormat: "P90 - {{instance_type}}",
							RefID:        "B",
						},
						{
							Expr:         `histogram_quantile(0.95, rate(r2_bench_latency_ms_bucket[5m]))`,
							LegendFormat: "P95 - {{instance_type}}",
							RefID:        "C",
						},
						{
							Expr:         `histogram_quantile(0.99, rate(r2_bench_latency_ms_bucket[5m]))`,
							LegendFormat: "P99 - {{instance_type}}",
							RefID:        "D",
						},
					},
					FieldConfig: FieldConfig{
						Defaults: Defaults{
							Color: Color{Mode: "palette-classic"},
							Custom: Custom{
								AxisLabel:     "",
								AxisPlacement: "auto",
								BarAlignment:  0,
								DrawStyle:     "line",
								FillOpacity:   10,
								GradientMode:  "none",
								HideFrom:      HideFrom{Legend: false, Tooltip: false, Viz: false},
								LineInterpolation: "linear",
								LineWidth:     1,
								PointSize:     5,
								ScaleDistribution: ScaleDistribution{Type: "linear"},
								ShowPoints:    "never",
								SpanNulls:     false,
								Stacking:      Stacking{Group: "A", Mode: "none"},
								ThresholdsStyle: ThresholdsStyle{Mode: "off"},
							},
							Mappings: []interface{}{},
							Thresholds: Thresholds{
								Mode: "absolute",
								Steps: []ThresholdStep{
									{Color: "green", Value: 0},
									{Color: "yellow", Value: 100},
									{Color: "red", Value: 500},
								},
							},
							Unit: "ms",
						},
					},
				},
				// QPS Panel
				{
					ID:    3,
					Title: "Requests per Second",
					Type:  "timeseries",
					GridPos: GridPos{
						H: 8,
						W: 12,
						X: 0,
						Y: 8,
					},
					Targets: []Target{
						{
							Expr:         `rate(r2_bench_requests_total[5m])`,
							LegendFormat: "{{instance_type}} - C{{concurrency}}",
							RefID:        "A",
						},
					},
					FieldConfig: FieldConfig{
						Defaults: Defaults{
							Color: Color{Mode: "palette-classic"},
							Custom: Custom{
								AxisLabel:     "",
								AxisPlacement: "auto",
								BarAlignment:  0,
								DrawStyle:     "line",
								FillOpacity:   10,
								GradientMode:  "none",
								HideFrom:      HideFrom{Legend: false, Tooltip: false, Viz: false},
								LineInterpolation: "linear",
								LineWidth:     1,
								PointSize:     5,
								ScaleDistribution: ScaleDistribution{Type: "linear"},
								ShowPoints:    "never",
								SpanNulls:     false,
								Stacking:      Stacking{Group: "A", Mode: "none"},
								ThresholdsStyle: ThresholdsStyle{Mode: "off"},
							},
							Mappings: []interface{}{},
							Thresholds: Thresholds{
								Mode: "absolute",
								Steps: []ThresholdStep{
									{Color: "green", Value: 0},
									{Color: "red", Value: 1000},
								},
							},
							Unit: "reqps",
						},
					},
				},
				// Error Rate Panel
				{
					ID:    4,
					Title: "Error Rate",
					Type:  "timeseries",
					GridPos: GridPos{
						H: 8,
						W: 12,
						X: 12,
						Y: 8,
					},
					Targets: []Target{
						{
							Expr:         `rate(r2_bench_errors_total[5m])`,
							LegendFormat: "{{instance_type}} - {{error_type}}",
							RefID:        "A",
						},
					},
					FieldConfig: FieldConfig{
						Defaults: Defaults{
							Color: Color{Mode: "palette-classic"},
							Custom: Custom{
								AxisLabel:     "",
								AxisPlacement: "auto",
								BarAlignment:  0,
								DrawStyle:     "line",
								FillOpacity:   10,
								GradientMode:  "none",
								HideFrom:      HideFrom{Legend: false, Tooltip: false, Viz: false},
								LineInterpolation: "linear",
								LineWidth:     1,
								PointSize:     5,
								ScaleDistribution: ScaleDistribution{Type: "linear"},
								ShowPoints:    "never",
								SpanNulls:     false,
								Stacking:      Stacking{Group: "A", Mode: "none"},
								ThresholdsStyle: ThresholdsStyle{Mode: "off"},
							},
							Mappings: []interface{}{},
							Thresholds: Thresholds{
								Mode: "absolute",
								Steps: []ThresholdStep{
									{Color: "green", Value: 0},
									{Color: "yellow", Value: 0.1},
									{Color: "red", Value: 1},
								},
							},
							Unit: "reqps",
						},
					},
				},
				// Concurrency Panel
				{
					ID:    5,
					Title: "Current Concurrency",
					Type:  "stat",
					GridPos: GridPos{
						H: 4,
						W: 6,
						X: 0,
						Y: 16,
					},
					Targets: []Target{
						{
							Expr:         `r2_bench_concurrency`,
							LegendFormat: "{{instance_type}}",
							RefID:        "A",
						},
					},
					FieldConfig: FieldConfig{
						Defaults: Defaults{
							Color: Color{Mode: "thresholds"},
							Custom: Custom{
								AxisLabel:     "",
								AxisPlacement: "auto",
								BarAlignment:  0,
								DrawStyle:     "line",
								FillOpacity:   10,
								GradientMode:  "none",
								HideFrom:      HideFrom{Legend: false, Tooltip: false, Viz: false},
								LineInterpolation: "linear",
								LineWidth:     1,
								PointSize:     5,
								ScaleDistribution: ScaleDistribution{Type: "linear"},
								ShowPoints:    "never",
								SpanNulls:     false,
								Stacking:      Stacking{Group: "A", Mode: "none"},
								ThresholdsStyle: ThresholdsStyle{Mode: "off"},
							},
							Mappings: []interface{}{},
							Thresholds: Thresholds{
								Mode: "absolute",
								Steps: []ThresholdStep{
									{Color: "green", Value: 0},
									{Color: "yellow", Value: 50},
									{Color: "red", Value: 100},
								},
							},
							Unit: "short",
						},
					},
					Options: map[string]interface{}{
						"colorMode":   "value",
						"graphMode":   "area",
						"justifyMode": "auto",
						"orientation": "auto",
						"reduceOptions": map[string]interface{}{
							"calcs": []string{"lastNotNull"},
							"fields": "",
							"values": false,
						},
						"textMode": "auto",
					},
				},
				// CPU Utilization Panel
				{
					ID:    6,
					Title: "CPU Utilization",
					Type:  "timeseries",
					GridPos: GridPos{
						H: 4,
						W: 6,
						X: 6,
						Y: 16,
					},
					Targets: []Target{
						{
							Expr:         `r2_bench_cpu_utilization`,
							LegendFormat: "{{instance_type}}",
							RefID:        "A",
						},
					},
					FieldConfig: FieldConfig{
						Defaults: Defaults{
							Color: Color{Mode: "palette-classic"},
							Custom: Custom{
								AxisLabel:     "",
								AxisPlacement: "auto",
								BarAlignment:  0,
								DrawStyle:     "line",
								FillOpacity:   10,
								GradientMode:  "none",
								HideFrom:      HideFrom{Legend: false, Tooltip: false, Viz: false},
								LineInterpolation: "linear",
								LineWidth:     1,
								PointSize:     5,
								ScaleDistribution: ScaleDistribution{Type: "linear"},
								ShowPoints:    "never",
								SpanNulls:     false,
								Stacking:      Stacking{Group: "A", Mode: "none"},
								ThresholdsStyle: ThresholdsStyle{Mode: "off"},
							},
							Mappings: []interface{}{},
							Thresholds: Thresholds{
								Mode: "absolute",
								Steps: []ThresholdStep{
									{Color: "green", Value: 0},
									{Color: "yellow", Value: 70},
									{Color: "red", Value: 90},
								},
							},
							Unit: "percent",
						},
					},
				},
				// Network Utilization Panel
				{
					ID:    7,
					Title: "Network Utilization",
					Type:  "timeseries",
					GridPos: GridPos{
						H: 4,
						W: 6,
						X: 12,
						Y: 16,
					},
					Targets: []Target{
						{
							Expr:         `r2_bench_network_utilization{metric="link_utilization"}`,
							LegendFormat: "{{instance_type}}",
							RefID:        "A",
						},
					},
					FieldConfig: FieldConfig{
						Defaults: Defaults{
							Color: Color{Mode: "palette-classic"},
							Custom: Custom{
								AxisLabel:     "",
								AxisPlacement: "auto",
								BarAlignment:  0,
								DrawStyle:     "line",
								FillOpacity:   10,
								GradientMode:  "none",
								HideFrom:      HideFrom{Legend: false, Tooltip: false, Viz: false},
								LineInterpolation: "linear",
								LineWidth:     1,
								PointSize:     5,
								ScaleDistribution: ScaleDistribution{Type: "linear"},
								ShowPoints:    "never",
								SpanNulls:     false,
								Stacking:      Stacking{Group: "A", Mode: "none"},
								ThresholdsStyle: ThresholdsStyle{Mode: "off"},
							},
							Mappings: []interface{}{},
							Thresholds: Thresholds{
								Mode: "absolute",
								Steps: []ThresholdStep{
									{Color: "green", Value: 0},
									{Color: "yellow", Value: 70},
									{Color: "red", Value: 90},
								},
							},
							Unit: "percent",
						},
					},
				},
				// TCP Retransmits Panel
				{
					ID:    8,
					Title: "TCP Retransmits",
					Type:  "timeseries",
					GridPos: GridPos{
						H: 4,
						W: 6,
						X: 18,
						Y: 16,
					},
					Targets: []Target{
						{
							Expr:         `r2_bench_network_utilization{metric="tcp_retransmits"}`,
							LegendFormat: "{{instance_type}}",
							RefID:        "A",
						},
					},
					FieldConfig: FieldConfig{
						Defaults: Defaults{
							Color: Color{Mode: "palette-classic"},
							Custom: Custom{
								AxisLabel:     "",
								AxisPlacement: "auto",
								BarAlignment:  0,
								DrawStyle:     "line",
								FillOpacity:   10,
								GradientMode:  "none",
								HideFrom:      HideFrom{Legend: false, Tooltip: false, Viz: false},
								LineInterpolation: "linear",
								LineWidth:     1,
								PointSize:     5,
								ScaleDistribution: ScaleDistribution{Type: "linear"},
								ShowPoints:    "never",
								SpanNulls:     false,
								Stacking:      Stacking{Group: "A", Mode: "none"},
								ThresholdsStyle: ThresholdsStyle{Mode: "off"},
							},
							Mappings: []interface{}{},
							Thresholds: Thresholds{
								Mode: "absolute",
								Steps: []ThresholdStep{
									{Color: "green", Value: 0},
									{Color: "yellow", Value: 10},
									{Color: "red", Value: 100},
								},
							},
							Unit: "short",
						},
					},
				},
			},
		},
		FolderID:  0,
		Overwrite: true,
	}
}

// SaveDashboard saves the dashboard configuration to a JSON file
func SaveDashboard(dashboard *GrafanaDashboard, outputPath string) error {
	// Create output directory if it doesn't exist
	dir := filepath.Dir(outputPath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("failed to create output directory: %w", err)
	}

	// Marshal to JSON
	data, err := json.MarshalIndent(dashboard, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal dashboard: %w", err)
	}

	// Write to file
	if err := os.WriteFile(outputPath, data, 0644); err != nil {
		return fmt.Errorf("failed to write dashboard file: %w", err)
	}

	fmt.Printf("Dashboard saved to %s\n", outputPath)
	return nil
}

func main() {
	dashboard := CreateR2BenchmarkDashboard()
	
	outputPath := "grafana/r2-benchmark-dashboard.json"
	if err := SaveDashboard(dashboard, outputPath); err != nil {
		fmt.Printf("Error saving dashboard: %v\n", err)
		os.Exit(1)
	}
	
	fmt.Println("Grafana dashboard configuration created successfully!")
	fmt.Println("You can import this dashboard into Grafana using the JSON file.")
}
