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