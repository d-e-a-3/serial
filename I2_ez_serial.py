
# -*- coding: utf-8 -*-
"""
Created on Mon Dec 23 22:38:39 2024

@author: clandersen
"""

import sys
import time  # Import for timestamp handling
from PyQt5.QtWidgets import (
    QApplication, QVBoxLayout, QWidget, QPushButton, QLabel, QComboBox, QTextEdit
)
from pyqtgraph import PlotWidget, mkPen
from Serial import Serial


class MainApp(QWidget):
    def __init__(self):
        super().__init__()
        self.serial = Serial()
        self.log_display = None  # Declare log_display here to avoid AttributeError
        self.init_ui()

        # Data for plotting
        self.data_x = []  # Timestamps or indices
        self.data_y = []  # Incoming values

    def init_ui(self):
        self.setWindowTitle("Super Party Pants")
        self.setGeometry(100, 100, 600, 500)
    
        # Main layout
        layout = QVBoxLayout()
    
        # Port selection
        self.port_label = QLabel("Available Ports:")
        layout.addWidget(self.port_label)
    
        self.port_combo = QComboBox()
        layout.addWidget(self.port_combo)
    
        # Baud rate selection
        self.baudrate_label = QLabel("Baud Rate:")
        layout.addWidget(self.baudrate_label)
    
        self.baudrate_combo = QComboBox()
        self.baudrate_combo.addItems(["9600", "19200", "38400", "57600", "115200", "230400"])
        self.baudrate_combo.setCurrentText("115200")
        layout.addWidget(self.baudrate_combo)
    
        # Connect button
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_serial)
        layout.addWidget(self.connect_button)
    
        # Disconnect button
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self.disconnect_serial)
        self.disconnect_button.setEnabled(False)
        layout.addWidget(self.disconnect_button)
    
        # Status label
        self.status_label = QLabel("Status: Disconnected")
        layout.addWidget(self.status_label)
    
        # Log display
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        layout.addWidget(self.log_display)
    
        # Data Plot
        self.plot_widget = PlotWidget()
        self.plot_widget.setBackground("w")
        self.plot_widget.setTitle("Real-Time Data", color="b", size="12pt")
        self.plot_widget.setLabel("left", "Force (mN)", color="blue")  # Y-axis label
        self.plot_widget.setLabel("bottom", "Time (s)", color="blue")  # X-axis label
        # self.plot_widget.addLegend()
        self.plot_widget.showGrid(x=True, y=True)
        self.data_line = self.plot_widget.plot([], [], pen=mkPen(color="r", width=2), name="Force")
        layout.addWidget(self.plot_widget)
    
        # Send test data
        self.send_button = QPushButton("Send Test Data")
        self.send_button.clicked.connect(self.send_test_data)
        self.send_button.setEnabled(False)
        # layout.addWidget(self.send_button)
    
        self.setLayout(layout)
        self.refresh_ports()


    def refresh_ports(self):
        """
        Refresh the list of available serial ports.
        """
        try:
            ports = self.serial.get_port_names()
            self.port_combo.clear()
            if ports:
                self.port_combo.addItems(ports)
                self.log_display.append(f"Found ports: {', '.join(ports)}")
            else:
                self.port_combo.addItem("No Ports Found")
                self.log_display.append("No serial ports found.")
        except Exception as e:
            self.log_display.append(f"Error refreshing ports: {e}")

    def connect_serial(self):
        """
        Connect to the selected serial port with the chosen baud rate.
        """
        try:
            selected_port = self.port_combo.currentText()
            selected_baudrate = int(self.baudrate_combo.currentText())

            if "No Ports Found" in selected_port or not selected_port:
                self.status_label.setText("Status: No Ports Available")
                self.log_display.append("No available port selected.")
                return

            self.serial.setup_port(selected_port, selected_baudrate)
            if self.serial.open_port():
                self.status_label.setText(f"Status: Connected to {selected_port} at {selected_baudrate} baud")
                self.log_display.append(f"Connected to {selected_port} at {selected_baudrate} baud")
                self.serial.rx_signal.connect(self.handle_serial_data)
                self.send_button.setEnabled(True)
                self.disconnect_button.setEnabled(True)
                self.connect_button.setEnabled(False)
            else:
                self.status_label.setText("Status: Failed to Connect")
                self.log_display.append("Failed to open the serial port.")
        except Exception as e:
            self.status_label.setText("Status: Error")
            self.log_display.append(f"Error during connection: {e}")

    def disconnect_serial(self):
        """
        Disconnect the serial port and clean up.
        """
        try:
            if self.serial.isOpen():
                self.serial.close()
                self.status_label.setText("Status: Disconnected")
                self.log_display.append("Serial port closed.")
                self.send_button.setEnabled(False)
                self.disconnect_button.setEnabled(False)
                self.connect_button.setEnabled(True)
        except Exception as e:
            self.log_display.append(f"Error during disconnection: {e}")


    def handle_serial_data(self, data):
        """
        Append incoming serial data to the log, parse the numeric value, and update the plot.
        """
        try:
            # Log the received raw data
            self.log_display.append(f"Received: {data}")
    
            # Parse the value from the format "422558 V T_mN: -4.63"
            try:
                if "T_mN:" in data:
                    value_str = data.split("T_mN:")[1].strip()  # Extract value after "T_mN:"
                    value = float(value_str)  # Convert to float
                    timestamp = time.time()  # Current time in seconds since the epoch
    
                    # Add timestamp and value to the data lists
                    self.data_x.append(timestamp)
                    self.data_y.append(value)
    
                    # Remove data older than 10 seconds
                    ten_seconds_ago = timestamp - 10
                    while self.data_x and self.data_x[0] < ten_seconds_ago:
                        self.data_x.pop(0)
                        self.data_y.pop(0)
    
                    # Update the plot
                    self.data_line.setData(
                        [x - self.data_x[0] for x in self.data_x],  # Shift time to start at 0
                        self.data_y
                    )
    
                    # Adjust the x-axis range to the last 10 seconds
                    self.plot_widget.setXRange(0, 10, padding=0)
                    self.plot_widget.enableAutoRange(axis='y', enable=True)
                else:
                    self.log_display.append("Data format unrecognized. Expected 'T_mN:' field.")
            except ValueError:
                self.log_display.append("Failed to parse numeric value.")
        except Exception as e:
            self.log_display.append(f"Error handling received data: {e}")




    def send_test_data(self):
        """
        Send a test message through the serial port.
        """
        try:
            test_message = "42.0"  # Example numeric test message
            self.serial.send(test_message)
            self.log_display.append(f"Sent: {test_message}")
        except Exception as e:
            self.log_display.append(f"Error sending data: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec_())
