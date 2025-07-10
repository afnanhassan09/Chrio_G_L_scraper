from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import json
from typing import Dict, List, Optional
import re
import os
import zipfile
import shutil
import imaplib
import email
from email.mime.text import MIMEText
import email.utils
from dotenv import load_dotenv


class EmailVerificationHandler:
    def __init__(self, email_address, email_password, imap_server=None):
        self.email_address = email_address
        self.email_password = email_password
        self.imap_server = imap_server or self._detect_imap_server(email_address)
        self.connection = None

    def _detect_imap_server(self, email_address):
        """Auto-detect IMAP server based on email domain"""
        domain = email_address.split("@")[1].lower()

        servers = {
            "gmail.com": "imap.gmail.com",
            "outlook.com": "outlook.office365.com",
            "hotmail.com": "outlook.office365.com",
            "live.com": "outlook.office365.com",
            "yahoo.com": "imap.mail.yahoo.com",
            "ymail.com": "imap.mail.yahoo.com",
            "aol.com": "imap.aol.com",
            "icloud.com": "imap.mail.me.com",
            "me.com": "imap.mail.me.com",
            "mac.com": "imap.mail.me.com",
        }

        return servers.get(domain, "imap." + domain)

    def connect(self):
        """Connect to email server"""
        try:
            print(f"📧 Connecting to email server: {self.imap_server}")
            self.connection = imaplib.IMAP4_SSL(self.imap_server)
            self.connection.login(self.email_address, self.email_password)
            print("✅ Email connection established successfully")
            return True
        except Exception as e:
            print(f"❌ Email connection failed: {str(e)}")
            print("💡 Make sure you're using an app password for Gmail/Outlook")
            return False

    def disconnect(self):
        """Disconnect from email server"""
        if self.connection:
            try:
                self.connection.logout()
                print("📧 Email connection closed")
            except:
                pass

    def fetch_linkedin_verification_code(self, max_age_minutes=5):
        """Fetch the latest LinkedIn verification code from emails"""
        if not self.connection:
            if not self.connect():
                return None

        try:
            # Select inbox
            self.connection.select("INBOX")

            # Search for recent LinkedIn emails
            search_criteria = [
                'FROM "linkedin"',
                'FROM "noreply@linkedin.com"',
                'FROM "security@linkedin.com"',
                'SUBJECT "verification"',
                'SUBJECT "code"',
                'SUBJECT "security"',
            ]

            verification_code = None

            for criteria in search_criteria:
                try:
                    print(f"🔍 Searching emails with criteria: {criteria}")

                    # Search for emails from the last few minutes
                    typ, data = self.connection.search(None, criteria)

                    if data[0]:
                        email_ids = data[0].split()
                        # Check latest emails first
                        for email_id in reversed(
                            email_ids[-10:]
                        ):  # Check last 10 emails
                            typ, msg_data = self.connection.fetch(email_id, "(RFC822)")
                            email_message = email.message_from_bytes(msg_data[0][1])

                            # Check email age
                            date_tuple = email.utils.parsedate_tz(email_message["Date"])
                            if date_tuple:
                                email_timestamp = email.utils.mktime_tz(date_tuple)
                                current_timestamp = time.time()
                                age_minutes = (current_timestamp - email_timestamp) / 60

                                if age_minutes > max_age_minutes:
                                    continue  # Skip old emails

                            # Extract verification code
                            code = self._extract_verification_code(email_message)
                            if code:
                                print(f"✅ Found verification code: {code}")
                                return code

                except Exception as e:
                    print(f"⚠️ Search error for {criteria}: {str(e)}")
                    continue

            print("❌ No verification code found in recent emails")
            return None

        except Exception as e:
            print(f"❌ Error fetching verification code: {str(e)}")
            return None

    def _extract_verification_code(self, email_message):
        """Extract verification code from LinkedIn email"""
        try:
            # Get email content
            subject = email_message.get("Subject", "").lower()
            sender = email_message.get("From", "").lower()

            # Only process LinkedIn emails
            if "linkedin" not in sender:
                return None

            print(f"📧 Processing email: {subject}")

            # Get email body
            body = ""
            if email_message.is_multipart():
                for part in email_message.walk():
                    if part.get_content_type() == "text/plain":
                        body += part.get_payload(decode=True).decode()
                    elif part.get_content_type() == "text/html":
                        body += part.get_payload(decode=True).decode()
            else:
                body = email_message.get_payload(decode=True).decode()

            # Extract verification code patterns
            code_patterns = [
                r"verification code[:\s]+(\d{4,8})",  # "verification code: 123456"
                r"code[:\s]+(\d{4,8})",  # "code: 123456"
                r"enter[:\s]+(\d{4,8})",  # "enter: 123456"
                r"(\d{6})",  # standalone 6-digit number
                r"(\d{4})",  # standalone 4-digit number
                r"security code[:\s]+(\d{4,8})",  # "security code: 123456"
                r"pin[:\s]+(\d{4,8})",  # "PIN: 123456"
            ]

            for pattern in code_patterns:
                matches = re.findall(pattern, body, re.IGNORECASE)
                if matches:
                    # Return the first valid code (4-8 digits)
                    for match in matches:
                        if 4 <= len(match) <= 8 and match.isdigit():
                            print(f"🔍 Extracted code using pattern: {pattern}")
                            return match

            return None

        except Exception as e:
            print(f"⚠️ Error extracting code from email: {str(e)}")
            return None


class LinkedInScraper:
    def __init__(self, email_handler=None):
        self.driver = None
        self.wait = None
        self.email_handler = email_handler

    def create_proxy_auth_extension(
        self, proxy_host, proxy_port, proxy_user, proxy_pass
    ):
        """Creates a Chrome extension for proxy authentication"""
        manifest_json = """
        {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Chrome Proxy",
            "permissions": [
                "proxy",
                "tabs",
                "unlimitedStorage",
                "storage",
                "<all_urls>",
                "webRequest",
                "webRequestBlocking"
            ],
            "background": {
                "scripts": ["background.js"]
            },
            "minimum_chrome_version":"22.0.0"
        }
        """

        background_js = f"""
        var config = {{
            mode: "fixed_servers",
            rules: {{
                singleProxy: {{
                    scheme: "http",
                    host: "{proxy_host}",
                    port: parseInt({proxy_port})
                }},
                bypassList: ["localhost"]
            }}
        }};

        chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});

        chrome.webRequest.onAuthRequired.addListener(
            function(details) {{
                return {{
                    authCredentials: {{
                        username: "{proxy_user}",
                        password: "{proxy_pass}"
                    }}
                }};
            }},
            {{urls: ["<all_urls>"]}},
            ['blocking']
        );
        """

        pluginfile = "proxy_auth_plugin.zip"
        with zipfile.ZipFile(pluginfile, "w") as zp:
            zp.writestr("manifest.json", manifest_json)
            zp.writestr("background.js", background_js)
        return pluginfile

    def setup_driver(self):
        """Initialize the Chrome WebDriver with Bright Data rotating proxy"""
        options = webdriver.ChromeOptions()

        # Essential browser hardening and stealth options
        options.add_argument(
            "--headless=new"
        )  # ENABLED: Running in headless mode for AWS deployment
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--disable-features=VizDisplayCompositor")
        options.add_argument("--remote-debugging-port=9222")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-renderer-backgrounding")

        # Additional stealth options for server environments
        options.add_argument("--disable-crash-reporter")
        options.add_argument("--disable-in-process-stack-traces")
        options.add_argument("--disable-logging")
        options.add_argument("--disable-dev-tools")
        options.add_argument("--log-level=3")
        options.add_argument("--silent")

        # Window size for headless mode
        options.add_argument("--window-size=1920,1080")

        # Enhanced user agent for better stealth
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        )

        # 🔐 Bright Data proxy credentials (loaded from environment for security)
        load_dotenv()
        proxy_host = os.getenv("BRIGHTDATA_PROXY_HOST", "brd.superproxy.io")
        proxy_port = int(os.getenv("BRIGHTDATA_PROXY_PORT", "33335"))
        proxy_user = os.getenv(
            "BRIGHTDATA_PROXY_USER", "brd-customer-hl_37fca7c2-zone-linkedin_scraper"
        )
        proxy_pass = os.getenv("BRIGHTDATA_PROXY_PASS", "xo5nwe0e1bt2")

        print(f"🌐 Setting up Bright Data rotating proxy: {proxy_host}:{proxy_port}")

        # 🔌 Create and inject proxy authentication plugin
        proxy_plugin_path = None
        try:
            proxy_plugin_path = self.create_proxy_auth_extension(
                proxy_host, proxy_port, proxy_user, proxy_pass
            )
            options.add_extension(proxy_plugin_path)
            print("✅ Proxy authentication plugin created and loaded")
        except Exception as e:
            print(f"⚠️ Warning: Failed to create proxy plugin: {e}")
            print("🔄 Continuing without proxy - may face IP blocks")

        # Find Chrome binary with fallback logic
        chrome_binary = self._find_chrome_binary()
        if chrome_binary:
            print(f"🔍 Using Chrome binary: {chrome_binary}")
            options.binary_location = chrome_binary
        else:
            print("🔍 Chrome binary not found, using system default")

        # Use webdriver-manager with retry logic
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.chrome.service import Service

        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(
                    f"🚀 Setting up ChromeDriver (attempt {attempt + 1}/{max_retries})"
                )

                # Clear cache on retry attempts
                if attempt > 0:
                    print("🧹 Clearing webdriver-manager cache...")
                    cache_dir = os.path.expanduser("~/.wdm")
                    if os.path.exists(cache_dir):
                        shutil.rmtree(cache_dir)

                # Check if Chrome is available
                chrome_installed = self._check_chrome_installation()

                if chrome_installed:
                    driver_path = ChromeDriverManager().install()
                else:
                    print(
                        "⚠️ Chrome not detected, using fallback ChromeDriver version..."
                    )
                    driver_path = ChromeDriverManager(
                        version="120.0.6099.109"
                    ).install()

                print(f"📍 ChromeDriver path: {driver_path}")

                # Handle potential path issues (webdriver-manager sometimes returns wrong file)
                actual_driver_path = self._find_actual_chromedriver(driver_path)

                service = Service(actual_driver_path)
                self.driver = webdriver.Chrome(service=service, options=options)

                print("🎉 ChromeDriver setup successful with Bright Data proxy!")
                print("🤖 Browser is running in HEADLESS mode for AWS deployment")
                print(
                    "📧 Email verification automation will handle challenges automatically"
                )
                break

            except Exception as e:
                print(f"❌ Attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    error_msg = (
                        f"Failed to setup ChromeDriver after {max_retries} attempts. "
                    )
                    error_msg += f"Last error: {str(e)}"
                    raise RuntimeError(error_msg)
                time.sleep(2)

        # Clean up proxy plugin file after driver starts
        if proxy_plugin_path and os.path.exists(proxy_plugin_path):
            try:
                os.remove(proxy_plugin_path)
                print("🧹 Proxy plugin file cleaned up")
            except:
                pass  # Ignore cleanup errors

        self.wait = WebDriverWait(self.driver, 10)

    def _find_actual_chromedriver(self, driver_path):
        """Find the actual chromedriver executable from webdriver-manager path"""
        if os.path.isfile(driver_path):
            driver_dir = os.path.dirname(driver_path)
        else:
            driver_dir = driver_path

        # Look for chromedriver executable
        possible_names = ["chromedriver.exe", "chromedriver"]

        for name in possible_names:
            test_path = os.path.join(driver_dir, name)
            if os.path.exists(test_path):
                # Make executable if needed
                if not os.access(test_path, os.X_OK):
                    os.chmod(test_path, 0o755)
                return test_path

        # Search subdirectories if not found
        for root, dirs, files in os.walk(driver_dir):
            for name in possible_names:
                if name in files:
                    full_path = os.path.join(root, name)
                    if not os.access(full_path, os.X_OK):
                        os.chmod(full_path, 0o755)
                    return full_path

        raise FileNotFoundError(f"ChromeDriver executable not found in {driver_dir}")

    def login(self, email: str, password: str):
        """Login to LinkedIn"""
        import sys

        print("🔐 Initiating LinkedIn login...")
        sys.stdout.flush()  # Force immediate output
        self.driver.get("https://www.linkedin.com/login")

        # Enter email
        email_field = self.wait.until(
            EC.presence_of_element_located((By.ID, "username"))
        )
        email_field.send_keys(email)
        print("✅ Email entered")
        sys.stdout.flush()

        # Enter password
        password_field = self.driver.find_element(By.ID, "password")
        password_field.send_keys(password)
        print("✅ Password entered")
        sys.stdout.flush()

        # Click login button
        login_button = self.driver.find_element(
            By.CSS_SELECTOR, 'button[type="submit"]'
        )
        login_button.click()
        print("🔄 Login button clicked, waiting for authentication...")
        sys.stdout.flush()

        # Verify login success
        try:
            if self._verify_login_success():
                print("🎉 SUCCESS: Login successful! Reached LinkedIn homepage/feed")
                sys.stdout.flush()
            else:
                print("❌ FAILED: Login failed or could not reach LinkedIn homepage")
                sys.stdout.flush()
                raise Exception(
                    "❌ FAILED: Login failed or could not reach LinkedIn homepage"
                )
        except Exception as login_error:
            print(f"🚨 Login verification failed: {str(login_error)}")
            sys.stdout.flush()
            raise

    def _verify_login_success(self) -> bool:
        """Verify that login was successful by checking for LinkedIn homepage elements"""
        import time

        max_wait_time = 15  # Maximum wait time for login
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            try:
                current_url = self.driver.current_url
                print(f"📍 Current URL: {current_url}")
                import sys

                sys.stdout.flush()

                # Check if we're on the feed/homepage
                homepage_indicators = [
                    # LinkedIn feed/homepage selectors
                    'nav[aria-label="Primary Navigation"]',  # Main navigation bar
                    ".feed-container-theme",  # Feed container
                    ".share-box-feed-entry",  # Share box
                    ".scaffold-layout__main",  # Main layout
                    '[data-test-id="nav-top-secondary"]',  # Secondary navigation
                    ".global-nav",  # Global navigation
                    "header.global-nav",  # Header navigation
                ]

                for selector in homepage_indicators:
                    try:
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if element.is_displayed():
                            print(f"✅ Found homepage indicator: {selector}")
                            return True
                    except:
                        continue

                # Check for LinkedIn security challenges first
                if "linkedin.com/checkpoint/challenge" in current_url:
                    print("🔒 LinkedIn security challenge detected!")
                    sys.stdout.flush()
                    challenge_info = self._identify_challenge_type()
                    if challenge_info:
                        print(f"📋 Challenge Details: {challenge_info}")
                        sys.stdout.flush()

                        # Check if this is an email verification challenge
                        is_email_verification = any(
                            keyword in challenge_info.lower()
                            for keyword in [
                                "email",
                                "verification code",
                                "6-digit",
                                "4-digit",
                                "code input",
                            ]
                        )

                        verification_success = False

                        # Try automatic email verification first
                        if is_email_verification and self.email_handler:
                            print(
                                "📧 EMAIL VERIFICATION DETECTED - Attempting automatic resolution..."
                            )
                            sys.stdout.flush()

                            try:
                                # Wait a moment for the email to arrive
                                print(
                                    "⏳ Waiting 10 seconds for verification email to arrive..."
                                )
                                time.sleep(10)

                                # Fetch verification code from email
                                verification_code = (
                                    self.email_handler.fetch_linkedin_verification_code()
                                )

                                if verification_code:
                                    print(
                                        f"📧 Retrieved verification code from email: {verification_code}"
                                    )

                                    # Auto-fill the verification code
                                    if self._auto_fill_verification_code(
                                        verification_code
                                    ):
                                        print(
                                            "🎉 Automatic email verification successful!"
                                        )
                                        verification_success = True

                                        # Wait for page to process and check if successful
                                        time.sleep(3)
                                        current_url_after_auto = self.driver.current_url
                                        if (
                                            "linkedin.com/checkpoint/challenge"
                                            not in current_url_after_auto
                                        ):
                                            print(
                                                "✅ Successfully moved past challenge page automatically!"
                                            )
                                            sys.stdout.flush()
                                            continue  # Continue with login verification
                                    else:
                                        print(
                                            "❌ Failed to auto-fill verification code"
                                        )
                                else:
                                    print("❌ No verification code found in emails")

                            except Exception as auto_error:
                                print(
                                    f"❌ Automatic verification failed: {str(auto_error)}"
                                )

                        # If automatic verification failed or not available, use manual intervention
                        if not verification_success:
                            if self.email_handler and is_email_verification:
                                print(
                                    "🔄 Automatic email verification failed, falling back to manual mode"
                                )

                            print("⏳ MANUAL INTERVENTION REQUIRED:")
                            print(
                                "   👆 Please complete the verification in the browser window"
                            )
                            print(
                                "   ⏰ Waiting 15 seconds for you to enter verification code..."
                            )
                            print(
                                "   🔄 Will automatically check if login succeeded after wait"
                            )
                            print(
                                "   ✋ Take your time - the loop will continue checking until success"
                            )
                            sys.stdout.flush()

                            # Wait 15 seconds for manual verification
                            time.sleep(15)

                        # Check current URL again after manual intervention
                        current_url_after = self.driver.current_url
                        print(f"📍 URL after manual intervention: {current_url_after}")
                        sys.stdout.flush()

                        # If still on challenge page, continue waiting in the loop
                        if "linkedin.com/checkpoint/challenge" in current_url_after:
                            print("⚠️ Still on challenge page - continuing to wait...")
                            sys.stdout.flush()
                            time.sleep(2)  # Brief pause before next iteration
                            continue
                        else:
                            print("✅ Successfully moved past challenge page!")
                            sys.stdout.flush()
                            # Continue with normal login verification below
                    else:
                        print("❌ Challenge type could not be determined")
                        print("⏳ Waiting 15 seconds anyway for manual intervention...")
                        sys.stdout.flush()
                        time.sleep(15)

                        # Check if we moved past the unknown challenge
                        current_url_after = self.driver.current_url
                        if "linkedin.com/checkpoint/challenge" in current_url_after:
                            print("❌ Still on unknown challenge page after waiting")
                            sys.stdout.flush()
                            raise Exception(
                                "LinkedIn security challenge encountered - type unknown, manual intervention failed"
                            )
                        else:
                            print("✅ Successfully moved past unknown challenge!")
                            sys.stdout.flush()

                # Check URL patterns that indicate successful login
                success_url_patterns = [
                    "linkedin.com/feed",
                    "linkedin.com/in/",
                    "linkedin.com/mynetwork",
                    "linkedin.com/jobs",
                    "linkedin.com/messaging",
                ]

                for pattern in success_url_patterns:
                    if pattern in current_url:
                        print(
                            f"✅ Detected successful login via URL pattern: {pattern}"
                        )
                        return True

                # Check for error indicators
                error_selectors = [
                    ".form__label--error",  # Login error messages
                    ".alert",  # General alerts
                    '[data-js-module-id="guest-frontend-challenge-default"]',  # Challenge page
                ]

                for selector in error_selectors:
                    try:
                        if self.driver.find_element(By.CSS_SELECTOR, selector):
                            print(f"❌ Login error detected: {selector}")
                            return False
                    except:
                        continue

                # If still on login page, continue waiting
                if (
                    "linkedin.com/login" in current_url
                    or "linkedin.com/uas/login" in current_url
                ):
                    print("⏳ Still on login page, waiting...")
                    time.sleep(1)
                    continue

                # If we're redirected somewhere else, assume success
                if "linkedin.com" in current_url and "login" not in current_url:
                    print(f"✅ Redirected away from login page to: {current_url}")
                    return True

                time.sleep(1)

            except Exception as e:
                print(f"⚠️ Error during login verification: {str(e)}")
                time.sleep(1)
                continue

        print("❌ Login verification timeout - could not confirm successful login")
        return False

    def _identify_challenge_type(self) -> str:
        """Identify the type of LinkedIn security challenge"""
        try:
            # Get page title and content for analysis
            page_title = self.driver.title.lower()
            page_source = self.driver.page_source.lower()

            print(f"📄 Page Title: {self.driver.title}")
            print(f"🔍 Analyzing challenge page...")
            import sys

            sys.stdout.flush()

            challenge_indicators = {
                # Two-Factor Authentication
                "2FA/Two-Factor Authentication": [
                    "two-factor",
                    "2fa",
                    "authenticator",
                    "verification code",
                    "enter the code",
                    "code from your",
                    "authentication app",
                ],
                # Phone Verification
                "Phone Verification": [
                    "phone number",
                    "mobile number",
                    "phone verification",
                    "enter your phone",
                    "verify phone",
                    "text message",
                ],
                # Email Verification
                "Email Verification": [
                    "email verification",
                    "verify your email",
                    "check your email",
                    "email code",
                    "confirmation email",
                ],
                # SMS Verification
                "SMS Verification": [
                    "sms",
                    "text message",
                    "verification code",
                    "mobile code",
                    "code sent to",
                    "enter the 6-digit",
                ],
                # CAPTCHA
                "CAPTCHA": [
                    "captcha",
                    "recaptcha",
                    "i'm not a robot",
                    "verify you're human",
                    "image verification",
                    "select all images",
                ],
                # Device Verification
                "Device Verification": [
                    "new device",
                    "unrecognized device",
                    "device verification",
                    "trust this device",
                    "remember this device",
                ],
                # Location/Unusual Activity
                "Unusual Activity": [
                    "unusual activity",
                    "suspicious activity",
                    "new location",
                    "different location",
                    "security alert",
                ],
                # Password/Security Questions
                "Additional Security": [
                    "security question",
                    "verify identity",
                    "additional verification",
                    "confirm your identity",
                    "account security",
                ],
            }

            detected_challenges = []

            # Check page content for challenge indicators
            for challenge_type, indicators in challenge_indicators.items():
                for indicator in indicators:
                    if indicator in page_source or indicator in page_title:
                        if challenge_type not in detected_challenges:
                            detected_challenges.append(challenge_type)
                        break

            # Look for specific form elements and inputs
            form_elements = {
                "PIN/Code Input": [
                    "input[type='tel']",
                    "input[name*='pin']",
                    "input[name*='code']",
                    "input[placeholder*='code']",
                    "input[placeholder*='verification']",
                ],
                "Phone Input": [
                    "input[type='tel']",
                    "input[name*='phone']",
                    "input[name*='mobile']",
                ],
                "Email Input": ["input[type='email']", "input[name*='email']"],
            }

            for element_type, selectors in form_elements.items():
                for selector in selectors:
                    try:
                        if self.driver.find_element(By.CSS_SELECTOR, selector):
                            if element_type not in detected_challenges:
                                detected_challenges.append(f"Form: {element_type}")
                            break
                    except:
                        continue

            # Check for specific challenge text content
            try:
                # Find main content areas
                content_selectors = [
                    ".challenge-page",
                    ".checkpoint-challenge",
                    ".challenge-content",
                    "main",
                    ".content",
                ]

                challenge_text = ""
                for selector in content_selectors:
                    try:
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        challenge_text += element.text.lower() + " "
                    except:
                        continue

                if challenge_text:
                    print(f"📝 Challenge page text snippet: {challenge_text[:200]}...")
                    sys.stdout.flush()

                    # Additional specific text analysis
                    if "enter the 6-digit code" in challenge_text:
                        detected_challenges.append("6-Digit Verification Code")
                    elif "enter the 4-digit code" in challenge_text:
                        detected_challenges.append("4-Digit PIN Code")
                    elif "authenticator app" in challenge_text:
                        detected_challenges.append("Authenticator App Required")
                    elif "robot" in challenge_text or "captcha" in challenge_text:
                        detected_challenges.append("Human Verification (CAPTCHA)")

            except Exception as e:
                print(f"⚠️ Error analyzing challenge text: {str(e)}")

            # Check for common challenge page elements
            challenge_elements = {
                "reCAPTCHA": ".g-recaptcha",
                "Phone Input": "input[type='tel']",
                "Code Input": "input[maxlength='6'], input[maxlength='4']",
                "Email Field": "input[type='email']",
                "Submit Button": "button[type='submit'], input[type='submit']",
            }

            found_elements = []
            for element_name, selector in challenge_elements.items():
                try:
                    if self.driver.find_element(By.CSS_SELECTOR, selector):
                        found_elements.append(element_name)
                except:
                    continue

            if found_elements:
                print(f"🎯 Detected page elements: {', '.join(found_elements)}")
                sys.stdout.flush()

            # Compile final challenge description
            if detected_challenges:
                challenge_summary = ", ".join(set(detected_challenges))
                if found_elements:
                    challenge_summary += (
                        f" | Elements found: {', '.join(found_elements)}"
                    )
                return challenge_summary
            elif found_elements:
                return f"Challenge with elements: {', '.join(found_elements)}"
            else:
                return "Unknown challenge type - manual review required"

        except Exception as e:
            print(f"⚠️ Error identifying challenge type: {str(e)}")
            return f"Challenge detection error: {str(e)}"

    def _auto_fill_verification_code(self, verification_code):
        """Automatically fill verification code in LinkedIn challenge form"""
        try:
            print(f"🤖 Attempting to auto-fill verification code: {verification_code}")

            # Common input field selectors for verification codes
            input_selectors = [
                "input[type='tel']",
                "input[name*='pin']",
                "input[name*='code']",
                "input[name*='verif']",
                "input[placeholder*='code']",
                "input[placeholder*='verification']",
                "input[placeholder*='PIN']",
                "input[id*='code']",
                "input[id*='pin']",
                "input[id*='verif']",
                "input[maxlength='6']",
                "input[maxlength='4']",
                "input[maxlength='8']",
                ".form-control",
                ".input-field",
            ]

            verification_input = None

            # Try to find the input field
            for selector in input_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            verification_input = element
                            print(f"✅ Found input field with selector: {selector}")
                            break
                    if verification_input:
                        break
                except Exception:
                    continue

            if not verification_input:
                print("❌ Could not find verification code input field")
                return False

            # Clear and enter the verification code
            verification_input.clear()
            verification_input.send_keys(verification_code)
            print(f"✅ Entered verification code: {verification_code}")

            # Give a moment for any field validation
            time.sleep(1)

            # Find and click submit button
            submit_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                "button[id*='submit']",
                "button[id*='verify']",
                "button[id*='continue']",
                ".btn-primary",
                ".submit-btn",
                ".verify-btn",
                ".continue-btn",
                "button:contains('Verify')",
                "button:contains('Submit')",
                "button:contains('Continue')",
                "[data-test-id*='submit']",
                "[data-test-id*='verify']",
            ]

            submit_button = None
            for selector in submit_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            submit_button = element
                            print(f"✅ Found submit button with selector: {selector}")
                            break
                    if submit_button:
                        break
                except Exception:
                    continue

            if submit_button:
                submit_button.click()
                print("✅ Clicked submit button")

                # Wait for processing
                print("⏳ Waiting for verification to process...")
                time.sleep(3)
                return True
            else:
                print("❌ Could not find submit button")
                return False

        except Exception as e:
            print(f"❌ Error auto-filling verification code: {str(e)}")
            return False

    def validate_linkedin_url(self, url: str) -> str:
        """Validate and format LinkedIn profile URL"""
        # Check if URL is None or empty
        if not url:
            raise ValueError("LinkedIn profile URL cannot be empty or None")

        # Remove any query parameters
        url = url.split("?")[0]

        # Handle different URL formats
        patterns = [
            r"https?://(?:www\.)?linkedin\.com/in/([^/]+)/?",  # Standard format
            r"https?://(?:www\.)?linkedin\.com/profile/view\?id=([^&]+)",  # ID format
            r"([^/]+)",  # Just the username
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                username = match.group(1)
                return f"https://www.linkedin.com/in/{username}/"

        raise ValueError("Invalid LinkedIn profile URL format")

    def get_profile_info(self, profile_url: str) -> Dict:
        """Extract information from a LinkedIn profile"""
        # Validate and format the URL
        formatted_url = self.validate_linkedin_url(profile_url)
        print(f"Accessing profile: {formatted_url}")

        self.driver.get(formatted_url)
        time.sleep(2)  # Reduced wait time

        # Scroll down to load more content
        self._scroll_page()

        profile_data = {
            "profile_url": formatted_url,
            "about": self._get_about(),
            "experience": self._get_experience(),
            "education": self._get_education(),
            "projects": self._get_projects(formatted_url),
            "certificates": self._get_certificates(formatted_url),
        }

        return profile_data

    def _scroll_page(self):
        """Scroll down the page to load more content"""
        SCROLL_PAUSE_TIME = 1  # Reduced pause time
        last_height = self.driver.execute_script("return document.body.scrollHeight")

        # Scroll more times to load posts and other content
        for _ in range(5):  # Increased from 3 to 5
            # Scroll down
            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            time.sleep(SCROLL_PAUSE_TIME)

            # Calculate new scroll height
            new_height = self.driver.execute_script("return document.body.scrollHeight")

            # Break if no more content
            if new_height == last_height:
                break
            last_height = new_height

    def _get_about(self) -> Optional[str]:
        """Extract about section"""
        try:
            # Try different selectors for about section
            selectors = [
                '.yozeCfRsmxqzgPSAFUghMVylfzjWitoNfLlqTd span[aria-hidden="true"]',  # More specific selector
                ".yozeCfRsmxqzgPSAFUghMVylfzjWitoNfLlqTd",  # Original selector
                ".display-flex.ph5.pv3 .inline-show-more-text",
                ".pv-shared-text-with-see-more-text .inline-show-more-text",
                ".pv-about__summary-text",
            ]

            for selector in selectors:
                try:
                    about_element = self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    text = about_element.text.strip()
                    if text:
                        return text
                except:
                    continue
            return None
        except TimeoutException:
            return None

    def _get_experience(self) -> List[Dict]:
        """Extract experience information"""
        experience_list = []
        try:
            # Try different selectors for experience section
            selectors = [
                "#experience",  # New ID from HTML
                "#experience-section",
                ".experience-section",
                ".pv-experience-section",
            ]

            for selector in selectors:
                try:
                    experience_section = self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )

                    # Find the parent section that contains the experience list
                    parent_section = experience_section.find_element(
                        By.XPATH,
                        './ancestor::section[contains(@class, "artdeco-card")]',
                    )

                    # Try different selectors for experience items based on new HTML structure
                    item_selectors = [
                        "li.artdeco-list__item",  # New structure
                        ".experience-item",
                        ".pv-entity__position-group-pager",
                        ".pv-entity__summary-info",
                    ]

                    for item_selector in item_selectors:
                        experience_items = parent_section.find_elements(
                            By.CSS_SELECTOR, item_selector
                        )
                        if experience_items:
                            for item in experience_items:
                                try:
                                    # Extract job title - try multiple selectors
                                    title = self._get_element_text(
                                        item,
                                        [
                                            '.display-flex.align-items-center.mr1.hoverable-link-text.t-bold span[aria-hidden="true"]',
                                            ".hoverable-link-text.t-bold span",
                                            ".experience-item__title",
                                            ".pv-entity__name",
                                            ".pv-entity__summary-info h3",
                                        ],
                                    )

                                    # Extract company name - try multiple selectors
                                    company = self._get_element_text(
                                        item,
                                        [
                                            '.t-14.t-normal span[aria-hidden="true"]',
                                            ".experience-item__subtitle",
                                            ".pv-entity__secondary-title",
                                            ".pv-entity__company-name",
                                        ],
                                    )

                                    # Extract duration - try multiple selectors
                                    duration = self._get_element_text(
                                        item,
                                        [
                                            '.t-14.t-normal.t-black--light .pvs-entity__caption-wrapper[aria-hidden="true"]',
                                            '.t-14.t-normal.t-black--light span[aria-hidden="true"]',
                                            ".experience-item__duration",
                                            ".pv-entity__date-range span:nth-child(2)",
                                            ".pv-entity__date-range",
                                        ],
                                    )

                                    # Extract location if available
                                    location = self._get_element_text(
                                        item,
                                        [
                                            '.t-14.t-normal.t-black--light span[aria-hidden="true"]:last-child',
                                            ".pv-entity__location span",
                                        ],
                                    )

                                    # Clean up company name (remove extra text like "· Internship")
                                    if company:
                                        company_parts = company.split(" · ")
                                        company_name = company_parts[0]
                                        job_type = (
                                            company_parts[1]
                                            if len(company_parts) > 1
                                            else None
                                        )
                                    else:
                                        company_name = company
                                        job_type = None

                                    if title or company_name:
                                        exp_data = {
                                            "title": title,
                                            "company": company_name,
                                            "duration": duration,
                                            "location": location,
                                        }
                                        if job_type:
                                            exp_data["job_type"] = job_type

                                        experience_list.append(exp_data)
                                except Exception as e:
                                    print(f"Error extracting experience item: {e}")
                                    continue

                            if experience_list:
                                break

                    if experience_list:
                        break

                except Exception as e:
                    print(
                        f"Error finding experience section with selector {selector}: {e}"
                    )
                    continue

        except TimeoutException:
            print("Timeout waiting for experience section")
            pass

        return experience_list

    def _get_education(self) -> List[Dict]:
        """Extract education information"""
        education_list = []
        try:
            # Try different selectors for education section
            selectors = [
                "#education",  # New ID pattern
                "#education-section",
                ".education-section",
                ".pv-education-section",
            ]

            for selector in selectors:
                try:
                    education_section = self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )

                    # Find the parent section that contains the education list
                    try:
                        parent_section = education_section.find_element(
                            By.XPATH,
                            './ancestor::section[contains(@class, "artdeco-card")]',
                        )
                    except:
                        parent_section = education_section

                    # Try different selectors for education items based on new HTML structure
                    item_selectors = [
                        "li.artdeco-list__item",  # New structure
                        ".education-item",
                        ".pv-education-entity",
                        ".pv-entity__summary-info",
                    ]

                    for item_selector in item_selectors:
                        education_items = parent_section.find_elements(
                            By.CSS_SELECTOR, item_selector
                        )
                        if education_items:
                            for item in education_items:
                                try:
                                    # Extract school name - try multiple selectors
                                    school = self._get_element_text(
                                        item,
                                        [
                                            '.display-flex.align-items-center.mr1.hoverable-link-text.t-bold span[aria-hidden="true"]',
                                            ".hoverable-link-text.t-bold span",
                                            ".education-item__school-name",
                                            ".pv-entity__school-name",
                                            ".pv-entity__degree-name",
                                        ],
                                    )

                                    # Extract degree - try multiple selectors
                                    degree = self._get_element_text(
                                        item,
                                        [
                                            '.t-14.t-normal span[aria-hidden="true"]',
                                            ".education-item__degree-name",
                                            ".pv-entity__degree-name",
                                            ".pv-entity__fos",
                                        ],
                                    )

                                    # Extract duration - try multiple selectors
                                    duration = self._get_element_text(
                                        item,
                                        [
                                            '.t-14.t-normal.t-black--light .pvs-entity__caption-wrapper[aria-hidden="true"]',
                                            '.t-14.t-normal.t-black--light span[aria-hidden="true"]',
                                            ".education-item__duration",
                                            ".pv-entity__dates span:nth-child(2)",
                                            ".pv-entity__dates",
                                        ],
                                    )

                                    if school or degree:
                                        education_list.append(
                                            {
                                                "school": school,
                                                "degree": degree,
                                                "duration": duration,
                                            }
                                        )
                                except Exception as e:
                                    print(f"Error extracting education item: {e}")
                                    continue

                            if education_list:
                                break

                    if education_list:
                        break

                except Exception as e:
                    print(
                        f"Error finding education section with selector {selector}: {e}"
                    )
                    continue

        except TimeoutException:
            print("Timeout waiting for education section")
            pass

        return education_list

    def _get_projects(self, main_profile_url: str) -> List[Dict]:
        """Extract projects data"""
        projects_list = []
        try:
            print("Looking for projects section...")

            # First check if any projects section exists at all
            initial_check_selectors = [
                'a[href*="/details/projects"]',
                'a[id*="navigation-index-see-all-projects"]',
                'a[href*="projects"]',
                'button[aria-label*="projects"]',
                "#projects",
                ".projects-section",
                ".pv-projects-section",
            ]

            projects_exist = False
            for selector in initial_check_selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    projects_exist = True
                    break

            if not projects_exist:
                print(
                    "No projects section found on this profile. Skipping projects extraction."
                )
                return projects_list

            # Try to find and click "Show all projects" button
            try:
                # Look for projects section button
                projects_button_selectors = [
                    'a[href*="/details/projects"]',
                    'a[id*="navigation-index-see-all-projects"]',
                    'a[href*="projects"]',
                    'button[aria-label*="projects"]',
                ]

                projects_button = None
                for selector in projects_button_selectors:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        element_text = element.text.lower()
                        href = element.get_attribute("href") or ""

                        if (
                            "show all" in element_text and "project" in element_text
                        ) or "/details/projects" in href:
                            projects_button = element
                            print(
                                f"Found projects button with text: '{element.text}' and href: '{href}'"
                            )
                            break

                    if projects_button:
                        break

                if projects_button:
                    # Navigate to projects page
                    projects_url = projects_button.get_attribute("href")
                    print(f"Navigating to projects page: {projects_url}")
                    self.driver.get(projects_url)
                    time.sleep(3)  # Wait for projects page to load

                    # Extract all projects from the projects page
                    projects_list = self._extract_projects_from_page()

                    # Navigate back to main profile
                    print(f"Navigating back to main profile: {main_profile_url}")
                    self.driver.get(main_profile_url)
                    time.sleep(2)  # Wait for main page to load

                else:
                    print(
                        "No 'Show all projects' button found, trying to extract from main page"
                    )
                    projects_list = self._extract_projects_from_main_page()

            except Exception as e:
                print(f"Error navigating to projects section: {e}")
                # Fallback to main page extraction
                projects_list = self._extract_projects_from_main_page()

        except Exception as e:
            print(f"Error getting projects: {e}")
            print("Continuing without projects data...")

        print(f"Total projects found: {len(projects_list)}")
        return projects_list

    def _extract_projects_from_page(self) -> List[Dict]:
        """Extract projects from the dedicated projects page"""
        projects_list = []
        try:
            print("Extracting projects from projects page...")

            # Wait for the projects page to load
            time.sleep(2)

            # Scroll to load all projects
            self._scroll_page()

            # Try different selectors for project items on the dedicated page
            project_selectors = [
                "li.pvs-list__paged-list-item",  # Main container for project items
                "li.artdeco-list__item.pvs-list__item--line-separated",  # More specific selector
                "li.artdeco-list__item",  # Main container for project items
                ".pvs-list__item",
                'div[data-view-name="profile-component-entity"]',
            ]

            for selector in project_selectors:
                try:
                    project_elements = self.driver.find_elements(
                        By.CSS_SELECTOR, selector
                    )
                    if project_elements:
                        print(
                            f"Found {len(project_elements)} projects with selector: {selector}"
                        )

                        for i, element in enumerate(project_elements):
                            try:
                                print(
                                    f"Processing project {i+1}/{len(project_elements)}"
                                )
                                project_data = self._extract_project_data(element)
                                if project_data:
                                    # Check for duplicates by title
                                    is_duplicate = any(
                                        proj.get("title") == project_data.get("title")
                                        for proj in projects_list
                                    )
                                    if not is_duplicate:
                                        projects_list.append(project_data)
                                        print(
                                            f"Added project: {project_data.get('title', 'Unknown')}"
                                        )
                                    else:
                                        print(
                                            f"Skipped duplicate project: {project_data.get('title', 'Unknown')}"
                                        )
                            except Exception as e:
                                print(f"Error extracting project {i+1}: {e}")
                                continue

                        if projects_list:
                            break

                except Exception as e:
                    print(f"Error with selector {selector}: {e}")
                    continue

        except Exception as e:
            print(f"Error extracting projects from page: {e}")

        return projects_list

    def _extract_projects_from_main_page(self) -> List[Dict]:
        """Fallback method to extract projects from main profile page"""
        projects_list = []
        try:
            print("Extracting projects from main profile page...")

            # Try to find projects section on main page - use non-blocking find_elements
            selectors = [
                "#projects",
                ".projects-section",
                ".pv-projects-section",
            ]

            for selector in selectors:
                try:
                    # Use find_elements instead of wait.until to avoid timeout exceptions
                    projects_sections = self.driver.find_elements(
                        By.CSS_SELECTOR, selector
                    )

                    if not projects_sections:
                        continue

                    projects_section = projects_sections[0]
                    print(f"Found projects section with selector: {selector}")

                    # Find parent section
                    try:
                        parent_section = projects_section.find_element(
                            By.XPATH,
                            './ancestor::section[contains(@class, "artdeco-card")]',
                        )
                    except:
                        parent_section = projects_section

                    # Extract visible projects
                    project_items = parent_section.find_elements(
                        By.CSS_SELECTOR, "li.artdeco-list__item"
                    )

                    if project_items:
                        print(f"Found {len(project_items)} projects on main page")
                        for item in project_items:
                            try:
                                project_data = self._extract_project_data(item)
                                if project_data:
                                    projects_list.append(project_data)
                            except:
                                continue

                    if projects_list:
                        break

                except Exception as e:
                    print(f"Error with main page selector {selector}: {e}")
                    continue

            if not projects_list:
                print("No projects found on main profile page")

        except Exception as e:
            print(f"Error extracting projects from main page: {e}")

        return projects_list

    def _extract_project_data(self, project_element) -> Optional[Dict]:
        """Extract data from a single project"""
        try:
            project_data = {}

            # Extract project title - try multiple selectors
            title_selectors = [
                '.display-flex.align-items-center.mr1.t-bold span[aria-hidden="true"]',
                '.hoverable-link-text.t-bold span[aria-hidden="true"]',
                '.t-bold span[aria-hidden="true"]',
                '.display-flex.align-items-center.mr1.hoverable-link-text.t-bold span[aria-hidden="true"]',
            ]

            title = self._get_element_text(project_element, title_selectors)
            if title:
                project_data["title"] = title

            # Extract project duration
            duration_selectors = [
                '.t-14.t-normal span[aria-hidden="true"]',
                ".t-14.t-normal",
                '.pvs-entity__caption-wrapper span[aria-hidden="true"]',
            ]

            duration = self._get_element_text(project_element, duration_selectors)
            if duration:
                project_data["duration"] = duration

            # Extract project description
            description_selectors = [
                '.inline-show-more-text span[aria-hidden="true"]',
                '.bdZjlATLciupslqErVKaEhgLJmpKCjM span[aria-hidden="true"]',
                '.t-14.t-normal.t-black.display-flex.align-items-center span[aria-hidden="true"]',
            ]

            description = self._get_element_text(project_element, description_selectors)
            if description:
                project_data["description"] = description

            # Extract associated skills
            try:
                skills_elements = project_element.find_elements(
                    By.CSS_SELECTOR,
                    ".hoverable-link-text.display-flex.align-items-center.t-14.t-normal.t-black strong",
                )
                if skills_elements:
                    skills_text = skills_elements[0].text.strip()
                    project_data["skills"] = skills_text
            except:
                pass

            # Extract external links/URLs
            try:
                link_elements = project_element.find_elements(
                    By.CSS_SELECTOR, 'a[href]:not([href*="linkedin.com"])'
                )
                if link_elements:
                    external_links = []
                    for link in link_elements:
                        href = link.get_attribute("href")
                        if href and href.startswith("http"):
                            link_data = {"url": href}

                            # Try to get link title
                            try:
                                link_title_element = link.find_element(
                                    By.CSS_SELECTOR,
                                    '.t-14.t-bold.break-words span[aria-hidden="true"]',
                                )
                                link_data["title"] = link_title_element.text.strip()
                            except:
                                pass

                            external_links.append(link_data)

                    if external_links:
                        project_data["external_links"] = external_links
            except:
                pass

            # Only return if we have at least a title
            if project_data.get("title"):
                return project_data

        except Exception as e:
            print(f"Error extracting individual project data: {e}")

        return None

    def _get_certificates(self, main_profile_url: str) -> List[Dict]:
        """Extract certificates and licenses data"""
        certificates_list = []
        try:
            print("Looking for certificates section...")

            # First check if any certificates section exists at all
            initial_check_selectors = [
                'a[href*="/details/certifications"]',
                'a[id*="navigation-index-see-all-licenses-and-certifications"]',
                'a[href*="certifications"]',
                'button[aria-label*="certificates"]',
                'button[aria-label*="licenses"]',
                "#licenses_and_certifications",
                "#certifications",
                ".licenses-certifications-section",
                ".pv-certifications-section",
            ]

            certificates_exist = False
            for selector in initial_check_selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    certificates_exist = True
                    break

            if not certificates_exist:
                print(
                    "No certificates section found on this profile. Skipping certificates extraction."
                )
                return certificates_list

            # Try to find and click "Show all certificates" button
            try:
                # Look for certificates section button
                certificates_button_selectors = [
                    'a[href*="/details/certifications"]',
                    'a[id*="navigation-index-see-all-licenses-and-certifications"]',
                    'a[href*="certifications"]',
                    'button[aria-label*="certificates"]',
                    'button[aria-label*="licenses"]',
                ]

                certificates_button = None
                for selector in certificates_button_selectors:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        element_text = element.text.lower()
                        href = element.get_attribute("href") or ""

                        if (
                            "show all" in element_text
                            and (
                                "certificate" in element_text
                                or "license" in element_text
                            )
                        ) or "/details/certifications" in href:
                            certificates_button = element
                            print(
                                f"Found certificates button with text: '{element.text}' and href: '{href}'"
                            )
                            break

                    if certificates_button:
                        break

                if certificates_button:
                    # Navigate to certificates page
                    certificates_url = certificates_button.get_attribute("href")
                    print(f"Navigating to certificates page: {certificates_url}")
                    self.driver.get(certificates_url)
                    time.sleep(3)  # Wait for certificates page to load

                    # Extract all certificates from the certificates page
                    certificates_list = self._extract_certificates_from_page()

                    # Navigate back to main profile
                    print(f"Navigating back to main profile: {main_profile_url}")
                    self.driver.get(main_profile_url)
                    time.sleep(2)  # Wait for main page to load

                else:
                    print(
                        "No 'Show all certificates' button found, trying to extract from main page"
                    )
                    certificates_list = self._extract_certificates_from_main_page()

            except Exception as e:
                print(f"Error navigating to certificates section: {e}")
                # Fallback to main page extraction
                certificates_list = self._extract_certificates_from_main_page()

        except Exception as e:
            print(f"Error getting certificates: {e}")
            print("Continuing without certificates data...")

        print(f"Total certificates found: {len(certificates_list)}")
        return certificates_list

    def _extract_certificates_from_page(self) -> List[Dict]:
        """Extract certificates from the dedicated certificates page"""
        certificates_list = []
        try:
            print("Extracting certificates from certificates page...")

            # Wait for the certificates page to load
            time.sleep(2)

            # Scroll to load all certificates
            self._scroll_page()

            # Try different selectors for certificate items on the dedicated page
            certificate_selectors = [
                "li.pvs-list__paged-list-item",  # Main container for certificate items
                "li.artdeco-list__item.pvs-list__item--line-separated",  # More specific selector
                "li.artdeco-list__item",
                ".pvs-list__item",
                'div[data-view-name="profile-component-entity"]',
            ]

            for selector in certificate_selectors:
                try:
                    certificate_elements = self.driver.find_elements(
                        By.CSS_SELECTOR, selector
                    )
                    if certificate_elements:
                        print(
                            f"Found {len(certificate_elements)} certificates with selector: {selector}"
                        )

                        for i, element in enumerate(certificate_elements):
                            try:
                                print(
                                    f"Processing certificate {i+1}/{len(certificate_elements)}"
                                )
                                certificate_data = self._extract_certificate_data(
                                    element
                                )
                                if certificate_data:
                                    # Check for duplicates by title
                                    is_duplicate = any(
                                        cert.get("title")
                                        == certificate_data.get("title")
                                        for cert in certificates_list
                                    )
                                    if not is_duplicate:
                                        certificates_list.append(certificate_data)
                                        print(
                                            f"Added certificate: {certificate_data.get('title', 'Unknown')}"
                                        )
                                    else:
                                        print(
                                            f"Skipped duplicate certificate: {certificate_data.get('title', 'Unknown')}"
                                        )
                            except Exception as e:
                                print(f"Error extracting certificate {i+1}: {e}")
                                continue

                        if certificates_list:
                            break

                except Exception as e:
                    print(f"Error with selector {selector}: {e}")
                    continue

        except Exception as e:
            print(f"Error extracting certificates from page: {e}")

        return certificates_list

    def _extract_certificates_from_main_page(self) -> List[Dict]:
        """Fallback method to extract certificates from main profile page"""
        certificates_list = []
        try:
            print("Extracting certificates from main profile page...")

            # Try to find certificates section on main page
            selectors = [
                "#licenses_and_certifications",
                "#certifications",
                ".licenses-certifications-section",
                ".pv-certifications-section",
            ]

            for selector in selectors:
                try:
                    # Use find_elements instead of wait.until to avoid timeout exceptions
                    certificates_sections = self.driver.find_elements(
                        By.CSS_SELECTOR, selector
                    )

                    if not certificates_sections:
                        continue

                    certificates_section = certificates_sections[0]
                    print(f"Found certificates section with selector: {selector}")

                    # Find parent section
                    try:
                        parent_section = certificates_section.find_element(
                            By.XPATH,
                            './ancestor::section[contains(@class, "artdeco-card")]',
                        )
                    except:
                        parent_section = certificates_section

                    # Extract visible certificates
                    certificate_items = parent_section.find_elements(
                        By.CSS_SELECTOR, "li.artdeco-list__item"
                    )

                    if certificate_items:
                        print(
                            f"Found {len(certificate_items)} certificates on main page"
                        )
                        for item in certificate_items:
                            try:
                                certificate_data = self._extract_certificate_data(item)
                                if certificate_data:
                                    certificates_list.append(certificate_data)
                            except:
                                continue

                    if certificates_list:
                        break

                except Exception as e:
                    print(f"Error with main page selector {selector}: {e}")
                    continue

            if not certificates_list:
                print("No certificates found on main profile page")

        except Exception as e:
            print(f"Error extracting certificates from main page: {e}")

        return certificates_list

    def _extract_certificate_data(self, certificate_element) -> Optional[Dict]:
        """Extract data from a single certificate"""
        try:
            certificate_data = {}

            # Extract certificate title - try multiple selectors
            title_selectors = [
                '.display-flex.align-items-center.mr1.hoverable-link-text.t-bold span[aria-hidden="true"]',
                '.hoverable-link-text.t-bold span[aria-hidden="true"]',
                '.display-flex.align-items-center.mr1.t-bold span[aria-hidden="true"]',
                '.t-bold span[aria-hidden="true"]',
            ]

            title = self._get_element_text(certificate_element, title_selectors)
            if title:
                certificate_data["title"] = title

            # Extract issuing organization
            organization_selectors = [
                '.t-14.t-normal span[aria-hidden="true"]',
                ".t-14.t-normal",
            ]

            organization = self._get_element_text(
                certificate_element, organization_selectors
            )
            if organization:
                certificate_data["issuing_organization"] = organization

            # Extract issue date and expiry
            date_selectors = [
                '.t-14.t-normal.t-black--light .pvs-entity__caption-wrapper[aria-hidden="true"]',
                '.t-14.t-normal.t-black--light span[aria-hidden="true"]',
                '.pvs-entity__caption-wrapper span[aria-hidden="true"]',
            ]

            # Get all date-related text elements
            date_elements = []
            for selector in date_selectors:
                try:
                    elements = certificate_element.find_elements(
                        By.CSS_SELECTOR, selector
                    )
                    for elem in elements:
                        text = elem.text.strip()
                        if text and (
                            "issued" in text.lower()
                            or "expired" in text.lower()
                            or any(
                                month in text.lower()
                                for month in [
                                    "jan",
                                    "feb",
                                    "mar",
                                    "apr",
                                    "may",
                                    "jun",
                                    "jul",
                                    "aug",
                                    "sep",
                                    "oct",
                                    "nov",
                                    "dec",
                                ]
                            )
                        ):
                            date_elements.append(text)
                except:
                    continue

            # Parse issue and expiry dates
            for date_text in date_elements:
                if "issued" in date_text.lower():
                    certificate_data["issue_date"] = date_text
                elif "expired" in date_text.lower():
                    certificate_data["expiry_date"] = date_text

            # Extract credential ID
            try:
                credential_elements = certificate_element.find_elements(
                    By.CSS_SELECTOR,
                    '.t-14.t-normal.t-black--light span[aria-hidden="true"]',
                )
                for elem in credential_elements:
                    text = elem.text.strip()
                    if "credential id" in text.lower():
                        certificate_data["credential_id"] = text
                        break
            except:
                pass

            # Extract associated skills
            try:
                skills_elements = certificate_element.find_elements(
                    By.CSS_SELECTOR,
                    '.display-flex.align-items-center.t-14.t-normal.t-black span[aria-hidden="true"]',
                )
                for elem in skills_elements:
                    text = elem.text.strip()
                    if text and "skills:" in text.lower():
                        # Extract skills part after "Skills:"
                        skills_part = text.split("Skills:")[-1].strip()
                        certificate_data["skills"] = skills_part
                        break
            except:
                pass

            # Extract external credential links
            try:
                # Look for "Show credential" buttons
                credential_buttons = certificate_element.find_elements(
                    By.CSS_SELECTOR,
                    'a[aria-label*="Show credential"], a[href]:not([href*="linkedin.com"])',
                )

                external_links = []
                for button in credential_buttons:
                    href = button.get_attribute("href")
                    if href and href.startswith("http") and "linkedin.com" not in href:
                        link_data = {"url": href, "type": "credential"}

                        # Try to get button text
                        button_text = button.text.strip()
                        if button_text:
                            link_data["text"] = button_text

                        external_links.append(link_data)

                if external_links:
                    certificate_data["external_links"] = external_links
            except:
                pass

            # Extract certificate documents/PDFs
            try:
                document_links = certificate_element.find_elements(
                    By.CSS_SELECTOR, 'a[href*="single-media-viewer"]'
                )

                documents = []
                for link in document_links:
                    href = link.get_attribute("href")
                    if href:
                        doc_data = {"url": href, "type": "document"}

                        # Try to get document title
                        try:
                            doc_title_element = link.find_element(
                                By.CSS_SELECTOR,
                                '.t-14.t-bold.break-words span[aria-hidden="true"]',
                            )
                            doc_data["title"] = doc_title_element.text.strip()
                        except:
                            pass

                        documents.append(doc_data)

                if documents:
                    certificate_data["documents"] = documents
            except:
                pass

            # Only return if we have at least a title
            if certificate_data.get("title"):
                return certificate_data

        except Exception as e:
            print(f"Error extracting individual certificate data: {e}")

        return None

    def _get_element_text(self, element, selectors: List[str]) -> Optional[str]:
        """Try multiple selectors to get element text"""
        for selector in selectors:
            try:
                text_element = element.find_element(By.CSS_SELECTOR, selector)
                return text_element.text.strip()
            except NoSuchElementException:
                continue
        return None

    def _check_chrome_installation(self) -> bool:
        """Check if Chrome browser is installed on the system"""
        import subprocess
        import platform

        chrome_commands = []
        system = platform.system().lower()

        if system == "windows":
            chrome_commands = [
                "chrome.exe",
                "google-chrome.exe",
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            ]
        else:  # Linux/Mac
            chrome_commands = [
                "google-chrome",
                "google-chrome-stable",
                "google-chrome-beta",
                "google-chrome-dev",
                "chromium-browser",
                "chromium",
            ]

        for cmd in chrome_commands:
            try:
                result = subprocess.run(
                    [cmd, "--version"], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    print(f"Found Chrome: {cmd} - {result.stdout.strip()}")
                    return True
            except (
                subprocess.TimeoutExpired,
                subprocess.CalledProcessError,
                FileNotFoundError,
            ):
                continue

        print("Chrome browser not found on system")
        return False

    def _find_chrome_binary(self) -> Optional[str]:
        """Find Chrome binary in common installation locations"""
        possible_paths = [
            # Linux
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
            "/opt/google/chrome/chrome",
            "/snap/bin/chromium",
            # Windows
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            # macOS
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]

        for path in possible_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                return path
        return None

    def _install_chromedriver_manually(self) -> Optional[str]:
        """Manual ChromeDriver installation for server environments"""
        import subprocess
        import platform
        import urllib.request
        import zipfile
        import tempfile

        try:
            print("Attempting manual ChromeDriver installation...")

            # Determine system architecture
            system = platform.system().lower()
            machine = platform.machine().lower()

            if system == "linux":
                if "x86_64" in machine or "amd64" in machine:
                    driver_url = "https://chromedriver.storage.googleapis.com/120.0.6099.109/chromedriver_linux64.zip"
                    driver_name = "chromedriver"
                else:
                    print("Unsupported Linux architecture")
                    return None
            elif system == "windows":
                driver_url = "https://chromedriver.storage.googleapis.com/120.0.6099.109/chromedriver_win32.zip"
                driver_name = "chromedriver.exe"
            elif system == "darwin":  # macOS
                driver_url = "https://chromedriver.storage.googleapis.com/120.0.6099.109/chromedriver_mac64.zip"
                driver_name = "chromedriver"
            else:
                print(f"Unsupported system: {system}")
                return None

            # Create temp directory for download
            with tempfile.TemporaryDirectory() as temp_dir:
                zip_path = os.path.join(temp_dir, "chromedriver.zip")

                print(f"Downloading ChromeDriver from: {driver_url}")
                urllib.request.urlretrieve(driver_url, zip_path)

                # Extract the driver
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(temp_dir)

                # Find the extracted driver
                extracted_driver = os.path.join(temp_dir, driver_name)
                if not os.path.exists(extracted_driver):
                    # Sometimes it's in a subdirectory
                    for root, dirs, files in os.walk(temp_dir):
                        if driver_name in files:
                            extracted_driver = os.path.join(root, driver_name)
                            break

                if not os.path.exists(extracted_driver):
                    print("Failed to extract ChromeDriver")
                    return None

                # Create final destination
                final_dir = os.path.expanduser("~/.chromedriver")
                os.makedirs(final_dir, exist_ok=True)
                final_path = os.path.join(final_dir, driver_name)

                # Copy driver to final location
                import shutil

                shutil.copy2(extracted_driver, final_path)

                # Make executable
                os.chmod(final_path, 0o755)

                print(f"ChromeDriver manually installed at: {final_path}")
                return final_path

        except Exception as e:
            print(f"Manual ChromeDriver installation failed: {e}")
            return None

    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()


def scrape_linkedin_profile(
    applicant_id: str,
    profile_url: str,
    email: str = None,
    password: str = None,
    email_password: str = None,
    enable_email_verification: bool = True,
) -> Dict:

    # Validate required parameters
    if not profile_url:
        raise ValueError("LinkedIn profile URL is required")

    if not applicant_id:
        raise ValueError("Applicant ID is required")

    if not email or not password:
        load_dotenv()
        email = email or os.getenv("LINKEDIN_EMAIL")
        password = password or os.getenv("LINKEDIN_PASSWORD")

        if not email or not password:
            raise ValueError(
                "LinkedIn credentials not found. Please provide email and password or set them in .env file"
            )

    # Setup email verification handler if enabled
    email_handler = None
    if enable_email_verification:
        # Get email password from parameter or environment
        if not email_password:
            load_dotenv()
            email_password = os.getenv("EMAIL_PASSWORD") or os.getenv(
                "EMAIL_APP_PASSWORD"
            )

        if email_password:
            try:
                print("📧 Setting up email verification handler...")
                email_handler = EmailVerificationHandler(email, email_password)
                if email_handler.connect():
                    print("✅ Email verification handler ready")
                else:
                    print(
                        "⚠️ Email connection failed - continuing without email automation"
                    )
                    email_handler = None
            except Exception as e:
                print(f"⚠️ Email handler setup failed: {str(e)}")
                print("🔄 Continuing without email automation")
                email_handler = None
        else:
            print("⚠️ No email password provided - email verification disabled")
            print(
                "💡 Set EMAIL_PASSWORD environment variable to enable email automation"
            )

    # Initialize the scraper
    scraper = LinkedInScraper(email_handler=email_handler)
    scraper.setup_driver()

    try:
        print(f"🎯 Starting LinkedIn scraper for applicant: {applicant_id}")
        print(f"🔗 Target profile: {profile_url}")
        print(f"👤 Using email: {email}")
        print("🤖 HEADLESS MODE: Automated email verification enabled")
        print("📧 Email challenges will be handled automatically")
        import sys

        sys.stdout.flush()

        # Login to LinkedIn
        print("🚀 Attempting LinkedIn login...")
        scraper.login(email, password)
        print("✅ Login completed successfully!")

        # Scrape profile information
        print("📊 Starting profile data extraction...")
        profile_data = scraper.get_profile_info(profile_url)
        print("✅ Profile data extraction completed!")

        data = {"id": applicant_id, "source": "linkedin", "data": profile_data}
        return data

    except Exception as e:
        # Print detailed error information before re-raising
        print(f"❌ LinkedIn scraping failed with error: {str(e)}")
        print(f"🔍 Error type: {type(e).__name__}")

        # Try to get more browser information if available
        try:
            if scraper.driver:
                current_url = scraper.driver.current_url
                page_title = scraper.driver.title
                print(f"📍 Browser was on: {current_url}")
                print(f"📄 Page title: {page_title}")

                # If it's a challenge page, try to identify it one more time
                if "checkpoint/challenge" in current_url:
                    print("🔒 Detected challenge page - attempting analysis...")
                    try:
                        challenge_info = scraper._identify_challenge_type()
                        print(f"📋 Challenge analysis: {challenge_info}")
                    except:
                        print("⚠️ Could not analyze challenge page")
        except:
            print("⚠️ Could not retrieve browser state information")

        # Re-raise with original error for proper error handling
        raise Exception(f"Error scraping profile: {str(e)}")
    finally:
        try:
            scraper.close()
            print("🧹 Browser closed successfully")
        except:
            print("⚠️ Warning: Could not close browser properly")

        # Disconnect email handler
        if email_handler:
            try:
                email_handler.disconnect()
            except:
                pass


# Example usage:
# if __name__ == "__main__":
#     # Example 1: Using environment variables
#     profile_data = scrape_linkedin_profile(
#         "https://www.linkedin.com/in/moaz-farooq-466326304/"
#     )

#     # Save to file
#     filename = f"profile_data_{int(time.time())}.json"
#     with open(filename, "w", encoding="utf-8") as f:
#         json.dump(profile_data, f, indent=4, ensure_ascii=False)
#     print(f"Profile data has been saved to '{filename}'")
