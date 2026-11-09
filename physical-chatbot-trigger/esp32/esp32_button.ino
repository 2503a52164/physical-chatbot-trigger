// Physical Chatbot Trigger - ESP32 firmware (DESIGN ONLY: not built or tested by the team)
// Publishes {"device_id":"esp32_button_1","action":"SINGLE_PRESS"} to AWS IoT Core
// when a push button on GPIO 4 is pressed. Libraries: PubSubClient, ArduinoJson.
// Put your real values in a local secrets.h (listed in .gitignore) - never commit them.

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "secrets.h"   // defines WIFI_SSID, WIFI_PASSWORD, AWS_IOT_ENDPOINT, AWS_CERT_CA, AWS_CERT_CRT, AWS_CERT_PRIVATE

const char* AWS_IOT_TOPIC = "esp32/button/trigger";
const char* THING_NAME    = "ESP32_Trigger";

#define BUTTON_PIN 4
bool lastButtonState = HIGH;
unsigned long lastPressTime = 0;

WiFiClientSecure net;
PubSubClient client(net);

void connectAWS() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println("\nWi-Fi connected");

  net.setCACert(AWS_CERT_CA);
  net.setCertificate(AWS_CERT_CRT);
  net.setPrivateKey(AWS_CERT_PRIVATE);
  client.setServer(AWS_IOT_ENDPOINT, 8883);

  Serial.print("Connecting to AWS IoT Core");
  while (!client.connect(THING_NAME)) { Serial.print("."); delay(1000); }
  Serial.println("\nAWS IoT Core connected");
}

void publishTrigger() {
  StaticJsonDocument<200> doc;
  doc["device_id"] = "esp32_button_1";
  doc["action"] = "SINGLE_PRESS";
  char buf[256];
  serializeJson(doc, buf);
  Serial.println(client.publish(AWS_IOT_TOPIC, buf) ? "Trigger published" : "Publish failed");
}

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);   // button between GPIO 4 and GND
  connectAWS();
}

void loop() {
  if (!client.connected()) connectAWS();
  client.loop();
  bool state = digitalRead(BUTTON_PIN);
  if (lastButtonState == HIGH && state == LOW && millis() - lastPressTime > 1000) {  // 1 s debounce
    Serial.println("Button pressed");
    publishTrigger();
    lastPressTime = millis();
  }
  lastButtonState = state;
}
