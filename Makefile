.PHONY: all clean install package-linux package-macos package-windows requirements

PYTHON := python3
PIP := pip3
PYINSTALLER := pyinstaller

all: clean requirements

requirements:
	$(PIP) install -r requirements.txt

clean:
	rm -rf build/ dist/ __pycache__/ *.spec

install:
	$(PIP) install -r requirements.txt

package-linux: clean requirements
	$(PYINSTALLER) --onefile --name lut_applicator lut_batch.py
	mkdir -p dist/LUT-Applicator-Linux
	cp dist/lut_applicator dist/LUT-Applicator-Linux/
	cp README.md dist/LUT-Applicator-Linux/
	cd dist && tar -czvf LUT-Applicator-Linux.tar.gz LUT-Applicator-Linux/

package-macos: clean requirements
	$(PYINSTALLER) --onefile --name lut_applicator lut_batch.py
	mkdir -p dist/LUT-Applicator-macOS
	cp dist/lut_applicator dist/LUT-Applicator-macOS/
	cp README.md dist/LUT-Applicator-macOS/
	cd dist && zip -r LUT-Applicator-macOS.zip LUT-Applicator-macOS/

package-windows: clean requirements
	$(PYINSTALLER) --onefile --name lut_applicator.exe lut_batch.py
	mkdir -p dist/LUT-Applicator-Windows
	cp dist/lut_applicator.exe dist/LUT-Applicator-Windows/
	cp README.md dist/LUT-Applicator-Windows/
	cd dist && zip -r LUT-Applicator-Windows.zip LUT-Applicator-Windows/

package-all: package-linux package-macos package-windows 