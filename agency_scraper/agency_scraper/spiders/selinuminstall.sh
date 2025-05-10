# 1. Update package list
sudo apt-get update

# 2. Install common dependencies needed by Chrome
sudo apt-get install -y wget unzip fontconfig locales gconf-service libasound2 libatk1.0-0 libc6 libcairo2 libcups2 libdbus-1-3 libexpat1 libfontconfig1 libgcc1 libgconf-2-4 libgdk-pixbuf2.0-0 libglib2.0-0 libgtk-3-0 libnspr4 libpango-1.0-0 libpangocairo-1.0-0 libstdc++6 libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 libxdamage1 libxext6 libxfixes3 libxi6 libxrandr2 libxrender1 libxss1 libxtst6 ca-certificates fonts-liberation libappindicator1 libnss3 lsb-release xdg-utils libgbm1

# 3. Download the latest stable Chrome .deb package
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

# 4. Install Chrome (this might show dependency errors initially)
sudo dpkg -i google-chrome-stable_current_amd64.deb

# 5. Fix any broken dependencies from the Chrome install
sudo apt-get install -f -y

# 6. Verify Chrome installation (optional)
google-chrome --version
# Keep note of the major version number (e.g., 124)

# 7. Clean up the downloaded installer
rm google-chrome-stable_current_amd64.deb

# Install jq if you don't have it
sudo apt-get install -y jq

# Get the latest stable Chrome version (adjust if needed)
CHROME_VERSION=$(google-chrome --version | cut -d ' ' -f 3 | cut -d '.' -f 1)
echo "Detected Chrome major version: $CHROME_VERSION"

# Find the corresponding ChromeDriver download URL (using the CfT JSON endpoint)
# Note: This method relies on the CfT endpoints being up-to-date
DRIVER_URL=$(curl -s https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json | jq -r ".versions[] | select(.version | startswith(\"$CHROME_VERSION.\")) | .downloads.chromedriver[] | select(.platform==\"linux64\") | .url" | head -n 1)

if [ -z "$DRIVER_URL" ]; then
  echo "Could not automatically find ChromeDriver URL for Chrome $CHROME_VERSION. Please find it manually from https://googlechromelabs.github.io/chrome-for-testing/ and download using wget."
  # Example manual download (replace URL with the correct one):
  # wget -N https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/.../linux64/chromedriver-linux64.zip -O chromedriver-linux64.zip
  exit 1 # Exit if URL not found automatically
fi


echo "Downloading ChromeDriver from: $DRIVER_URL"
wget -N $DRIVER_URL -O chromedriver-linux64.zip

# Unzip ChromeDriver
unzip -o chromedriver-linux64.zip # Use -o to overwrite without prompting

# Clean up the zip file
rm chromedriver-linux64.zip

# Make ChromeDriver executable and move it to a standard location
# The path inside the zip might vary slightly, adjust if needed (e.g., it might be inside a directory)
# Check the zip contents first if unsure: unzip -l chromedriver-linux64.zip
# Assuming it extracts directly or into a known dir like 'chromedriver-linux64'
chmod +x chromedriver-linux64/chromedriver
sudo mv chromedriver-linux64/chromedriver /usr/local/bin/chromedriver

# Verify (optional)
chromedriver --version