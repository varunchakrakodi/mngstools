import sys
import os
import yaml
import psutil
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QLineEdit, QPushButton, QComboBox,
    QDoubleSpinBox, QSpinBox, QFileDialog, QTextEdit, QProgressBar,
    QMessageBox, QGroupBox, QToolBar, QToolButton, QMenu, QSizePolicy
)
from PySide6.QtCore import Qt, QProcess, QTimer, QUrl
from PySide6.QtGui import QFont, QDesktopServices, QAction


DARK_STYLE = """
    QMainWindow, QWidget {
        background-color: #1e1e1e;
        color: #e0e0e0;
    }
    QGroupBox {
        border: 1px solid #3e3e3e;
        border-radius: 6px;
        margin-top: 10px;
        padding-top: 10px;
        font-weight: bold;
        color: #ffffff;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 5px;
    }
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
        background-color: #2d2d2d;
        color: #ffffff;
        border: 1px solid #4a4a4a;
        padding: 4px;
        border-radius: 4px;
    }
    QPushButton, QToolButton {
        background-color: #3a3a3a;
        color: #ffffff;
        border: 1px solid #555555;
        padding: 5px 12px;
        border-radius: 4px;
    }
    QPushButton:hover, QToolButton:hover {
        background-color: #4a4a4a;
    }
    QMenu {
        background-color: #2d2d2d;
        color: #ffffff;
        border: 1px solid #4a4a4a;
    }
    QMenu::item:selected {
        background-color: #0d6efd;
    }
    QToolBar {
        background-color: #252526;
        border-bottom: 1px solid #3e3e3e;
        spacing: 6px;
    }
    QProgressBar {
        border: 1px solid #4a4a4a;
        border-radius: 4px;
        text-align: center;
        background-color: #2d2d2d;
        color: #ffffff;
    }
    QProgressBar::chunk {
        background-color: #0d6efd;
    }
"""

LIGHT_STYLE = """
    QMainWindow, QWidget {
        background-color: #f8f9fa;
        color: #212529;
    }
    QGroupBox {
        border: 1px solid #ced4da;
        border-radius: 6px;
        margin-top: 10px;
        padding-top: 10px;
        font-weight: bold;
        color: #212529;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 5px;
    }
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
        background-color: #ffffff;
        color: #212529;
        border: 1px solid #ced4da;
        padding: 4px;
        border-radius: 4px;
    }
    QPushButton, QToolButton {
        background-color: #e9ecef;
        color: #212529;
        border: 1px solid #ced4da;
        padding: 5px 12px;
        border-radius: 4px;
    }
    QPushButton:hover, QToolButton:hover {
        background-color: #dde2e6;
    }
    QMenu {
        background-color: #ffffff;
        color: #212529;
        border: 1px solid #ced4da;
    }
    QMenu::item:selected {
        background-color: #0d6efd;
        color: #ffffff;
    }
    QToolBar {
        background-color: #e9ecef;
        border-bottom: 1px solid #ced4da;
        spacing: 6px;
    }
    QProgressBar {
        border: 1px solid #ced4da;
        border-radius: 4px;
        text-align: center;
        background-color: #ffffff;
        color: #212529;
    }
    QProgressBar::chunk {
        background-color: #0d6efd;
    }
"""


class KrakenGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kraken2 / Bracken Pipeline Runner")
        self.resize(1000, 860)

        self.process = None
        self.is_dark_theme = True

        self.init_ui()
        self.apply_theme()
        self.init_ram_monitor()

    def init_ui(self):
        # 1. Main Toolbar
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # First Time Use Dropdown Menu
        first_time_btn = QToolButton(self)
        first_time_btn.setText("🚀 First Time Use")
        first_time_btn.setPopupMode(QToolButton.InstantPopup)
        first_time_menu = QMenu(first_time_btn)

        action_get_conda = QAction("📦 Get Conda", self)
        action_get_conda.triggered.connect(self.get_conda)
        first_time_menu.addAction(action_get_conda)

        action_install_deps = QAction("⚙️ Install dependencies", self)
        action_install_deps.triggered.connect(self.install_dependencies)
        first_time_menu.addAction(action_install_deps)

        first_time_btn.setMenu(first_time_menu)
        toolbar.addWidget(first_time_btn)

        dl_action = QAction("🌐 Download database", self)
        dl_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl("https://benlangmead.github.io/aws-indexes/k2")))
        toolbar.addAction(dl_action)

        help_action = QAction("❓ Help", self)
        help_action.triggered.connect(self.show_help)
        toolbar.addAction(help_action)

        credits_action = QAction("📜 Credits", self)
        credits_action.triggered.connect(self.show_credits)
        toolbar.addAction(credits_action)

        clean_action = QAction("🧹 Cleanup", self)
        clean_action.triggered.connect(self.run_cleanup)
        toolbar.addAction(clean_action)

        # Expanding Spacer for Theme Switcher
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        self.theme_btn = QPushButton("☀️ Switch to Light Mode")
        self.theme_btn.clicked.connect(self.toggle_theme)
        toolbar.addWidget(self.theme_btn)

        # 2. Central Layout & Form Inputs
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        grid_group = QGroupBox("Pipeline Setup & File Paths")
        grid = QGridLayout()

        # Snakemake File
        grid.addWidget(QLabel("Snakemake File:"), 0, 0)
        self.snakefile_input = QLineEdit()
        grid.addWidget(self.snakefile_input, 0, 1)
        btn_snake = QPushButton("Browse")
        btn_snake.clicked.connect(lambda: self.browse_file(self.snakefile_input, "Snakefile (*Snakefile* *.smk *.py *.*)"))
        grid.addWidget(btn_snake, 0, 2)

        # FASTQ Reads
        grid.addWidget(QLabel("FASTQ Reads Directory:"), 1, 0)
        self.fastq_input = QLineEdit()
        grid.addWidget(self.fastq_input, 1, 1)
        btn_fastq = QPushButton("Browse")
        btn_fastq.clicked.connect(lambda: self.browse_dir(self.fastq_input))
        grid.addWidget(btn_fastq, 1, 2)

        # Output Folder
        grid.addWidget(QLabel("Output Directory:"), 2, 0)
        self.output_input = QLineEdit()
        grid.addWidget(self.output_input, 2, 1)
        btn_out = QPushButton("Browse")
        btn_out.clicked.connect(lambda: self.browse_dir(self.output_input))
        grid.addWidget(btn_out, 2, 2)

        # Database Folder
        grid.addWidget(QLabel("Database Directory:"), 3, 0)
        self.db_input = QLineEdit()
        grid.addWidget(self.db_input, 3, 1)
        btn_db = QPushButton("Browse")
        btn_db.clicked.connect(lambda: self.browse_dir(self.db_input))
        grid.addWidget(btn_db, 3, 2)

        # Host Genome Reference Input
        grid.addWidget(QLabel("Host Reference Genome:"), 4, 0)
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("/path/to/host/reference.fa")
        grid.addWidget(self.host_input, 4, 1)
        btn_host = QPushButton("Browse")
        btn_host.clicked.connect(lambda: self.browse_file(self.host_input, "FASTA Files (*.fa *.fasta *.fna *.*)"))
        grid.addWidget(btn_host, 4, 2)

        grid_group.setLayout(grid)
        main_layout.addWidget(grid_group)

        # 3. Parameters Section
        param_group = QGroupBox("Execution & Algorithm Parameters")
        param_layout = QHBoxLayout()

        param_layout.addWidget(QLabel("Kraken Confidence:"))
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.0, 1.0)
        self.confidence_spin.setSingleStep(0.01)
        self.confidence_spin.setValue(0.03)
        param_layout.addWidget(self.confidence_spin)

        param_layout.addWidget(QLabel("Bracken Level:"))
        self.bracken_combo = QComboBox()
        self.bracken_combo.addItems(["S", "D", "P", "C", "O", "F", "G"])
        param_layout.addWidget(self.bracken_combo)

        param_layout.addWidget(QLabel("Threads:"))
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 256)
        self.threads_spin.setValue(16)
        param_layout.addWidget(self.threads_spin)

        param_layout.addWidget(QLabel("Latency Wait (s):"))
        self.latency_spin = QSpinBox()
        self.latency_spin.setRange(60, 500)
        self.latency_spin.setValue(60)
        param_layout.addWidget(self.latency_spin)

        param_group.setLayout(param_layout)
        main_layout.addWidget(param_group)

        # 4. Action Buttons
        exec_layout = QHBoxLayout()
        self.run_btn = QPushButton("▶ Run Pipeline")
        self.run_btn.setStyleSheet("font-weight: bold; background-color: #2e7d32; color: white; padding: 6px;")
        self.run_btn.clicked.connect(self.run_pipeline)
        exec_layout.addWidget(self.run_btn)

        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("background-color: #c62828; color: white; padding: 6px;")
        self.stop_btn.clicked.connect(self.stop_process)
        exec_layout.addWidget(self.stop_btn)
        main_layout.addLayout(exec_layout)

        # 5. Terminal Console Output
        log_group = QGroupBox("Execution Console")
        log_layout = QVBoxLayout()
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Monospace", 9))
        log_layout.addWidget(self.log_view)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)

        # 6. Live Resource Bar
        ram_layout = QHBoxLayout()
        self.ram_label = QLabel("RAM Usage: Calculating...")
        self.ram_bar = QProgressBar()
        self.ram_bar.setRange(0, 100)
        ram_layout.addWidget(self.ram_label)
        ram_layout.addWidget(self.ram_bar)
        main_layout.addLayout(ram_layout)

    # --- First Time Use Actions ---
    def get_conda(self):
        cmd = "curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
        self.log_message(f"--- Downloading Miniconda Installer ---")
        self.log_message(f"Running: {cmd}\n")
        self.execute_command("curl", ["-O", "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"])

    def install_dependencies(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select install.sh File", filter="Shell Scripts (*install*.sh *.sh *.*)")
        if not file_path:
            return

        self.log_message(f"--- Running Dependency Installer ---")
        self.log_message(f"Script: {file_path}\n")
        self.execute_command("bash", [file_path])

    # --- Theme Toggling ---
    def toggle_theme(self):
        self.is_dark_theme = not self.is_dark_theme
        self.apply_theme()

    def apply_theme(self):
        if self.is_dark_theme:
            self.setStyleSheet(DARK_STYLE)
            self.log_view.setStyleSheet("background-color: #121212; color: #4af626; border: 1px solid #333333;")
            self.theme_btn.setText("☀️ Switch to Light Mode")
        else:
            self.setStyleSheet(LIGHT_STYLE)
            self.log_view.setStyleSheet("background-color: #212529; color: #f8f9fa; border: 1px solid #ced4da;")
            self.theme_btn.setText("🌙 Switch to Dark Mode")

    # --- Dialog Operations ---
    def browse_dir(self, target_line_edit):
        path = QFileDialog.getExistingDirectory(self, "Select Directory")
        if path:
            target_line_edit.setText(path)

    def browse_file(self, target_line_edit, file_filter):
        path, _ = QFileDialog.getOpenFileName(self, "Select File", filter=file_filter)
        if path:
            target_line_edit.setText(path)

    # --- Header Action Callbacks ---
    def show_help(self):
        snakefile = self.snakefile_input.text().strip()
        base_dir = Path(snakefile).parent if snakefile else Path.cwd()
        help_path = base_dir / "Help"

        if not help_path.exists():
            help_path = base_dir / "Help.txt"

        if help_path.exists():
            try:
                content = help_path.read_text()
                QMessageBox.information(self, "Help", content)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to read Help file: {e}")
        else:
            QMessageBox.warning(self, "Help Not Found", f"No 'Help' or 'Help.txt' file found in:\n{base_dir}")

    def show_credits(self):
        snakefile = self.snakefile_input.text().strip()
        base_dir = Path(snakefile).parent if snakefile else Path.cwd()
        credits_path = base_dir / "credits.txt"

        if credits_path.exists():
            try:
                content = credits_path.read_text()
                QMessageBox.information(self, "Credits", content)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to read credits.txt: {e}")
        else:
            QMessageBox.warning(self, "Credits Not Found", f"credits.txt not found in:\n{base_dir}")

    def run_cleanup(self):
        snakefile = self.snakefile_input.text().strip()
        base_dir = Path(snakefile).parent if snakefile else Path.cwd()
        clean_script = base_dir / "clean.sh"

        if not clean_script.exists():
            QMessageBox.warning(self, "File Missing", f"clean.sh not found in:\n{base_dir}")
            return

        self.log_message(f"--- Starting cleanup script: {clean_script} ---")
        self.execute_command("bash", [str(clean_script)])

    # --- Config & Execution ---
    def generate_config(self, out_dir):
        threads = self.threads_spin.value()
        db_path = self.db_input.text().strip()
        host_path = self.host_input.text().strip()

        config_data = {
            "fastq_dir": self.fastq_input.text().strip(),
            "output_dir": out_dir,
            "reference": host_path,
            "kraken_db": db_path,
            "bracken_db": db_path,
            "kraken_confidence": round(self.confidence_spin.value(), 2),
            "bracken_level": self.bracken_combo.currentText(),
            "bracken_threshold": 2,
            "trim_threads": threads,
            "map_threads": threads,
            "kraken_threads": threads
        }

        config_path = Path(out_dir) / "config_kraken2.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

        return config_path

    def run_pipeline(self):
        snakefile = self.snakefile_input.text().strip()
        fastq_dir = self.fastq_input.text().strip()
        out_dir = self.output_input.text().strip()
        db_dir = self.db_input.text().strip()
        host_ref = self.host_input.text().strip()

        if not all([snakefile, fastq_dir, out_dir, db_dir, host_ref]):
            QMessageBox.critical(self, "Validation Error", "All folder paths, the Host Reference, and the Snakefile must be specified.")
            return

        if not os.path.exists(snakefile):
            QMessageBox.critical(self, "File Error", f"Snakefile does not exist: {snakefile}")
            return

        if not os.path.exists(host_ref):
            QMessageBox.critical(self, "File Error", f"Host Reference file does not exist: {host_ref}")
            return

        os.makedirs(out_dir, exist_ok=True)

        try:
            config_file = self.generate_config(out_dir)
            self.log_message(f"Config successfully written to: {config_file}")
        except Exception as e:
            QMessageBox.critical(self, "Config Error", f"Failed to generate YAML config:\n{e}")
            return

        threads = str(self.threads_spin.value())
        latency_wait = str(self.latency_spin.value())

        args = [
            "-s", snakefile,
            "--configfile", str(config_file),
            "--cores", threads,
            "--latency-wait", latency_wait
        ]

        self.log_message(f"--- Launching Snakemake ---")
        self.log_message(f"Command: snakemake {' '.join(args)}\n")
        self.execute_command("snakemake", args)

    def execute_command(self, program, args):
        if self.process and self.process.state() == QProcess.Running:
            QMessageBox.warning(self, "Job Running", "A process is already active. Please wait or stop it.")
            return

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.handle_output)
        self.process.finished.connect(self.process_finished)

        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.process.start(program, args)

    def stop_process(self):
        if self.process and self.process.state() == QProcess.Running:
            self.process.terminate()
            self.log_message("\n--- Process termination requested by user. ---")

    def handle_output(self):
        data = self.process.readAllStandardOutput()
        stdout = bytes(data).decode("utf8", errors="replace")
        self.log_view.append(stdout.rstrip())
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    def process_finished(self, exit_code, exit_status):
        self.log_message(f"\n--- Execution completed with code: {exit_code} ---")
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def log_message(self, message):
        self.log_view.append(message)
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    # --- Live System Monitoring ---
    def init_ram_monitor(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_ram_usage)
        self.timer.start(1500)

    def update_ram_usage(self):
        ram = psutil.virtual_memory()
        used_gb = ram.used / (1024 ** 3)
        total_gb = ram.total / (1024 ** 3)
        self.ram_bar.setValue(int(ram.percent))
        self.ram_label.setText(f"RAM Usage: {used_gb:.1f} GB / {total_gb:.1f} GB ({ram.percent}%)")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KrakenGUI()
    window.show()
    sys.exit(app.exec())