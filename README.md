# mhm aka mioty-heat-mapper

mhm (mioty heat mapper) is a Python application for measuring network coverage
in mioty networks, to evaluate if a given setup is sufficient for covering a
site or location.

The tool aims to assist engineers, in figuring out suitable locations for mioty
base stations / mioty gateways by gathering and visualizing network coverage on
floor plans, aerial photos or any other visual representation of the world. It
assumes that the user has some familiarity with the way mioty works, and that
the user has a mioty network set up to publish uplinks via ACMQTTI 0.3.0.

This tool is forked from the [https://github.com/Nischay-Pro/wifi-heat-mapper]
by Nischay Mamidi, which in turn is heavily inspired by
[https://github.com/jantman/python-wifi-survey-heatmap] by
[Jason Antman](www.jasonantman.com).

## Functionality

This tool comes with a GUI that helps with recording network coverage values
easily gathered from within mioty networks: RSSI, SNR and eqSNR (an aggregate
across mioty bursts of an uplink). The general idea is to begin with a floor
plan, map, aerial photo or other 2D image representation of the location / site
to be measured. On that image it is then possible to select a measurement
location, for which traffic shall be recorded for a set of mioty EUIs. All
uplinks (initials and duplicates) will be recorded per-base-station until a
measurement is stopped and then used for generating the aggregate coverage maps
(overall and per-base-station).

# Installation (TODO)

The easiest way to install whm is via [pip](https://pip.pypa.io/en/stable/).

```bash
$ pip install whm
```

Alternatively, you can clone the repository and compile it.

```bash
$ git clone https://github.com/Nischay-Pro/wifi-heat-mapper.git
$ cd wifi-heat-mapper
$ python3 setup.py install
```

## Supported Platforms

- Operating System
  - Linux x86_64 (64 bit)

## Dependencies

To run the application, the following dependencies must be explicitly installed.
Transitive dependencies will be installed automatically.

- Python version: 3.12 (with Tkinter)
- PySimpleGUI >= 4.34.0, <= 4.60.3
- cairosvg >= 2.7.0
- matplotlib >= 3.8.0
- paho.mqtt >= 2.0.0

On Windows, GTK3 must be installed, as the application depends on libcairo-2. To
install GTK3, the easiest way is to install the precompiled binaries from
[https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases].

## Tkinter

By default Tkinter is not installed with Python and must be installed manually.

### Arch Linux and Manjaro

```bash
$ pacman -S tk
```

### Fedora, CentOS, RHEL and RockyLinux

```bash
$ dnf install python3-tkinter
```

### Debian and Ubuntu

```bash
$ apt install python3-tk
```

### openSUSE and SUSE Linux Enterprise

```bash
$ zypper install python3-tk
```

# Usage

## Configuration

A default configuration (`config.json`, unless specified using `--config`) can
be bootstrapped using:

```bash
$ mhm init
```

The `config.json` file is structured in three sections:

- The `configuration` section with various options, described below.
- The `locations` section, where measurement locations are tracked, plus
  measurement results obtained at the locations.
- The `stations` section, where base station locations are tracked.

Available configuration options:

| Option                       | Description                                                                         |
| ---------------------------- | ----------------------------------------------------------------------------------- |
| `colormap`                   | Picks a matplotlib colormap.                                                        |
| `contours`                   | The number of contour lines in the plot (e.g. 100).                                 |
| `dpi`                        | The resolution of the exported file, and of the display of an SVG map.              |
| `extrapolate`                | Adds four corner points with the value of `vmin` to fill the entire image.          |
| `factors`                    | A list of selected measurement factors (e.g. `rssi`, `snr`, ...).                   |
| `file_format`                | The export file format of the report (e.g. `png`, `pdf`, ...).                      |
| `modes`                      | The measurement interface(s) used to gather information (e.g. `acmqqti`, ...).      |
| `map_path`                   | The path to the background map.                                                     |
| `acmqtti_ac_eui`             | The AC EUI that is subscribed to in upper hex dashed (optional).                    |
| `acmqtti_ep_euis`            | The EP EUIs that are subscribed to in upper hex dashed (optional).                  |
| `acmqtti_broker`             | The `host:port` of the ACMQTTI broker. Mandatory for mode `acmqtti`.                |
| `acmqtti_broker_tls_ca_cert` | The path to the ACMQTTI broker TLS CA certificate (optional).                       |
| `acmqtti_broker_username`    | The username for the ACMQTTI broker (optional). Triggers a runtime password prompt. |

## Gathering metrics

To gather metrics, start the application with a

1. Start by Left-clicking on the canvas roughly at a position where you are
   capturing the metrics from. A gray circle with a blue outline will appear.

![GUI-2](images/gui-2.png)

2. Now right-click on the circle. You will be presented with a drop-down menu
   having 3 options.
   - Measure: Starts capturing metrics at this position.
   - Delete: Deletes the point and any measurements taken at this point.
   - Mark / Un-Mark as Station: Marks this point as a Base Station. This is
     purely informational at the moment, and produces an orange dot in the plot.

![GUI-3](images/gui-3.png)

3. Select "Measure" and ensure data is generated that can be logged. This can be
   done by regularly sending uplinks from a sensor at a given point. Measurement
   results are automatically saved (observe the console). Additional
   measurements can always be recorded by selecting "Measure" on a specific
   location again. The new results will be added to any previous results.

![GUI-4](images/gui-4.png)

4. Now move to a new position you want to measure from and select the rough
   position in the canvas.

5. The application requires at least 4 points to generate plots. It is strongly
   recommended to profile as many points as possible to increase the accuracy of
   the heatmap.

6. Once completed click on "Save Results" to save the metrics to the
   `config.json` file. You can then plot your metrics by pressing "Plot".

## Resuming from a previous state

To resume from a previous benchmarking state, simply repeat the command you used
to run the benchmarking initially. All results are stored in the configuration
file the user has specified originally.

## Plotting

Plots are generated either via the "Plot" button in the GUI or via the `plot`
command. The plot can be customized via the `config.json` file (colors,
resolution, format, ...).

```bash
$ mhm plot -c config.json
```

A subdirectory with the same name as the `config.json` file will be created,
which will contain the graphs that are configured in the `config.json` file (see
`factors`).

## Adding Information

Currently not a GUI-feature, additional information can be added for display in
the plots. If locations with negative coordinates (e.g. `X = -1` and `Y = -1`)
are added to the `stations` list in the `config.json` file, these locations will
be used as a lookup for a customized title description. To add such titles, add
stations with `"bs_key": "...the_bs_identifier..."` and
`"description": "Extra Description for the Plot Title"`.

## Examples

A sample configuration, including benchmark results and plots generated is
provided in the [examples](examples/SAMPLE.md) folder.

# Contributing

Pull requests are welcome. For significant changes, please open an issue first
to discuss what you would like to change.

Please make sure to run tests as appropriate.

# License

[GPLv3](https://choosealicense.com/licenses/gpl-3.0/)
