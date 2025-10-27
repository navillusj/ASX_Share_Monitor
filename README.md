# ASX Share Monitor 📈

The ASX Share Monitor is a desktop application built with Python and Tkinter (using the sv_ttk theme) that provides real-time monitoring and historical price charting for Australian Stock Exchange (ASX) shares. It fetches data using the yfinance library and uses Matplotlib for interactive chart visualization, complete with timezone handling and robust sorting features.

## ⚠️ Disclaimer and Limitation of Liability
BY USING THIS APPLICATION, YOU EXPRESSLY AGREE THAT YOUR USE IS AT YOUR SOLE RISK.

This software is provided "as is" without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and non-infringement.

The ASX Share Monitor is intended for informational and educational purposes only. The data provided is sourced from third-party APIs (yfinance) and should not be considered financial advice, investment recommendation, or a solicitation to buy or sell any financial instrument.

Limitation of Liability
In no event shall the author or copyright holders of this application be liable for any claims, damages, or other liability, whether in an action of contract, tort, or otherwise, arising from, out of, or in connection with the software or the use or other dealings in the software.

Data Accuracy: The accuracy of the data cannot be guaranteed. Data may be delayed, inaccurate, incomplete, or affected by API downtime.

No Financial Advice: You should consult with a qualified professional financial advisor before making any investment decisions.

Own Risk: Any decisions made based on the information or charts presented by this application are solely the user's responsibility.

## ✨ Key Features
Real-time Data: Fetches current price, open price, daily change, and hourly change for ASX-listed tickers (e.g., BHP.AX).

Interactive Charting: Displays historical stock data over various ranges (6 Months to 10 Minutes).

Intraday Timezone Adjustment: Charts automatically adjust time displays to your preferred timezone (Sydney, Perth, Brisbane).

Advanced Chart Control: Toggle individual stock lines on/off the Main Monitor chart to manage visual scaling of diverse stock prices.

Sortable Table: Sort the Main Monitor table by Price, Daily Change, Hourly Change, and more.

Customizable Settings: Persistent settings for default chart range and timezone.

## 🚀 Installation & Setup
This application can be run directly from the Python script or compiled into a standalone Windows executable (.exe) using PyInstaller.

Prerequisites
You need Python 3.8+ installed on your system.

Install Dependencies: Open your terminal or command prompt and install the required libraries:

```pip install tkinter numpy pandas matplotlib yfinance sv-ttk pillow pytz```

Running from Source
Save the Files: Save the main script as Share_monitor.py (or whatever your current name is).

Run the Application: Execute the script from your terminal:

```python Share_monitor.py```

## 📦 Building the Standalone Executable (.EXE)
To create a single, portable executable file (which includes the necessary assets like the logo), you need to use PyInstaller.

1. Requirements
Make sure you have PyInstaller installed:
pip install pyinstaller

2. Prepare Assets
Ensure you have your logo file (logo.png) and the Windows icon file (logo.ico) in the same directory as your main script.

3. PyInstaller Command
Run the following command in your terminal from the script's directory. This command packages the application, creates a single executable, sets the application icon, and bundles the logo image for the splash screen:

```pyinstaller --onefile --windowed --name "ASX_Share_Monitor" --icon="logo.ico" --add-data "logo.png:." "Share_monitor.py"```

5. Run the EXE
The compiled executable (ASX_Share_Monitor.exe) will be found in the newly created dist folder.

## 🛠️ Usage NotesAdding Stocks:

Enter the ASX ticker symbol (e.g., BHP) and click Add ASX Stock or simply press the Enter key while the input field is focused. The .AX extension is added automatically if missing.
Chart Visibility: On the Main Monitor tab, use the CHART ($\checkmark$/$\times$) column to click and toggle individual lines on or off the combined plot. This is useful for dealing with shares of vastly different values (e.g., a $100 stock and a $1 stock).
Settings: Access Settings to permanently set the default Timezone and Chart Range.
Tooltip: Hover your mouse over any line on the chart to display the historical price and time at that point, along with the latest daily and hourly change data.

