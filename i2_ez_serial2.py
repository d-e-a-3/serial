import sys
import time
import csv
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLabel, QComboBox,
    QTextEdit, QSpinBox
)
from pyqtgraph import PlotWidget, mkPen
from Serial import Serial

class MainApp(QWidget):
    def __init__(self):
        super().__init__()
        self.serial = Serial()
        self.log_display = None

        # QTimer for polling serial data
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll_serial_data)

        # QTimer for sampling duration
        self.duration_timer = QTimer(self)
        self.duration_timer.setSingleShot(True)
        self.duration_timer.timeout.connect(self.stop_sampling_due_to_duration)

        self._pending_data = []
        self.sampling_active = False

        self.init_ui()

        # Data for plotting
        self.data_x = []
        self.data_y = []

    def init_ui(self):
        self.setWindowTitle("Super Party Pants")
        self.setGeometry(100, 100, 600, 650)

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

        # Serial update frequency selection
        freq_layout = QHBoxLayout()
        freq_label = QLabel("Serial Update Frequency:")
        freq_layout.addWidget(freq_label)
        self.freq_combo = QComboBox()
        self.freq_options = [
            ("2 ms", 2),
            ("20 ms", 20),
            ("50 ms", 50),
            ("100 ms", 100),
            ("200 ms", 200),
        ]
        for label, _ in self.freq_options:
            self.freq_combo.addItem(label)
        self.freq_combo.setCurrentIndex(2)  # Default to 50 ms
        self.freq_combo.currentIndexChanged.connect(self.update_timer_interval)
        freq_layout.addWidget(self.freq_combo)
        layout.addLayout(freq_layout)

        # Sampling duration control
        duration_layout = QHBoxLayout()
        duration_label = QLabel("Sampling Duration (seconds):")
        duration_layout.addWidget(duration_label)
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 3600)
        self.duration_spin.setValue(10)
        duration_layout.addWidget(self.duration_spin)
        layout.addLayout(duration_layout)

        # Start/Stop Sampling buttons
        self.start_sampling_button = QPushButton("Start Sampling")
        self.start_sampling_button.clicked.connect(self.start_sampling)
        layout.addWidget(self.start_sampling_button)

        self.stop_sampling_button = QPushButton("Stop Sampling")
        self.stop_sampling_button.clicked.connect(self.stop_sampling)
        self.stop_sampling_button.setEnabled(False)
        layout.addWidget(self.stop_sampling_button)

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
        self.plot_widget.setLabel("left", "Force (mN)", color="blue")
        self.plot_widget.setLabel("bottom", "Time (s)", color="blue")
        self.plot_widget.showGrid(x=True, y=True)
        self.data_line = self.plot_widget.plot([], [], pen=mkPen(color="r", width=2), name="Force")
        layout.addWidget(self.plot_widget)

        # Export Data Button
        self.export_button = QPushButton("Export Data")
        self.export_button.clicked.connect(self.export_data)
        layout.addWidget(self.export_button)

        # Send test data
        self.send_button = QPushButton("Send Test Data")
        self.send_button.clicked.connect(self.send_test_data)
        self.send_button.setEnabled(False)
        # layout.addWidget(self.send_button)

        self.setLayout(layout)
        self.refresh_ports()

    def refresh_ports(self):
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
                self.serial.rx_signal.connect(self.buffer_serial_data)
                self.send_button.setEnabled(True)
                self.disconnect_button.setEnabled(True)
                self.connect_button.setEnabled(False)
                self._pending_data.clear()
                self.update_timer_interval()
            else:
                self.status_label.setText("Status: Failed to Connect")
                self.log_display.append("Failed to open the serial port.")
        except Exception as e:
            self.status_label.setText("Status: Error")
            self.log_display.append(f"Error during connection: {e}")

    def disconnect_serial(self):
        try:
            if self.serial.isOpen():
                self.serial.close()
                self.status_label.setText("Status: Disconnected")
                self.log_display.append("Serial port closed.")
                self.send_button.setEnabled(False)
                self.disconnect_button.setEnabled(False)
                self.connect_button.setEnabled(True)
                self.timer.stop()
                self.duration_timer.stop()
                self.stop_sampling()
        except Exception as e:
            self.log_display.append(f"Error during disconnection: {e}")

    def closeEvent(self, event):
        # Release serial port on app exit
        try:
            if self.serial.isOpen():
                self.serial.close()
        except Exception:
            pass
        event.accept()

    def start_sampling(self):
        duration_sec = self.duration_spin.value()
        self.log_display.append(f"Sampling started for {duration_sec} seconds.")
        self.sampling_active = True
        self.start_sampling_button.setEnabled(False)
        self.stop_sampling_button.setEnabled(True)
        self.duration_timer.start(duration_sec * 1000)
        self.timer.start()  # Start polling serial data at set interval

    def stop_sampling(self):
        if self.sampling_active:
            self.log_display.append("Sampling stopped.")
        self.sampling_active = False
        self.start_sampling_button.setEnabled(True)
        self.stop_sampling_button.setEnabled(False)
        self.duration_timer.stop()
        self.timer.stop()

    def stop_sampling_due_to_duration(self):
        self.log_display.append("Sampling duration completed.")
        self.stop_sampling()

    def buffer_serial_data(self, data):
        if self.sampling_active:
            self._pending_data.append(data)

    def poll_serial_data(self):
        while self._pending_data:
            data = self._pending_data.pop(0)
            self.handle_serial_data(data)

    def update_timer_interval(self):
        idx = self.freq_combo.currentIndex()
        interval_ms = self.freq_options[idx][1]
        self.timer.setInterval(interval_ms)

    def handle_serial_data(self, data):
        try:
            self.log_display.append(f"Received: {data}")
            try:
                if "T_mN:" in data:
                    value_str = data.split("T_mN:")[1].strip()
                    value = float(value_str)
                    timestamp = time.time()
                    self.data_x.append(timestamp)
                    self.data_y.append(value)

                    # Keep only points within the sampling window
                    duration = self.duration_spin.value()
                    window_start = timestamp - duration
                    while self.data_x and self.data_x[0] < window_start:
                        self.data_x.pop(0)
                        self.data_y.pop(0)

                    # Update the plot to show the whole duration
                    if self.data_x:
                        t0 = self.data_x[0]
                        x_data = [x - t0 for x in self.data_x]
                        self.data_line.setData(x_data, self.data_y)
                        self.plot_widget.setXRange(0, duration, padding=0)
                        self.plot_widget.enableAutoRange(axis='y', enable=True)
                else:
                    self.log_display.append("Data format unrecognized. Expected 'T_mN:' field.")
            except ValueError:
                self.log_display.append("Failed to parse numeric value.")
        except Exception as e:
            self.log_display.append(f"Error handling received data: {e}")

    def export_data(self):
        try:
            filename = "exported_data.csv"
            with open(filename, "w", newline="") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["Time", "Force (mN)"])
                for x, y in zip(self.data_x, self.data_y):
                    writer.writerow([x, y])
            self.log_display.append(f"Data exported to {filename}")
        except Exception as e:
            self.log_display.append(f"Export failed: {e}")

    def send_test_data(self):
        try:
            test_message = "42.0"
            self.serial.send(test_message)
            self.log_display.append(f"Sent: {test_message}")
        except Exception as e:
            self.log_display.append(f"Error sending data: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec_())
