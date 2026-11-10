#include <Arduino.h>
#include <math.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>
#include <Adafruit_BNO08x.h>
#include "BluetoothSerial.h"

#define I2C_SDA 21
#define I2C_SCL 22

BluetoothSerial SerialBT;

enum SensorType {
    SENSOR_NONE,
    SENSOR_BNO055,
    SENSOR_BNO08X
};

SensorType detectedSensor = SENSOR_NONE;
uint8_t sensorAddr = 0;
sh2_SensorId_t activeReport = SH2_ROTATION_VECTOR;

Adafruit_BNO055 bno055 = Adafruit_BNO055(55, 0x28, &Wire);
Adafruit_BNO08x bno08x;
sh2_SensorValue_t sensorValue;

unsigned long lastPrint = 0;
unsigned long lastPacketTime = 0;
unsigned long lastScanRetry = 0;
unsigned long recoveryCount = 0;

bool sendQuaternion(float w, float x, float y, float z) {
    float norm = w*w + x*x + y*y + z*z;
    if (!isfinite(norm) || norm < 0.25f || norm > 2.25f) return false;
    float scale = 1.0f / sqrtf(norm);
    w *= scale; x *= scale; y *= scale; z *= scale;
    char buf[64];
    snprintf(buf, sizeof(buf), "Q,%.4f,%.4f,%.4f,%.4f\n", w, x, y, z);
    Serial.print(buf);
    if (SerialBT.hasClient()) SerialBT.print(buf);
    lastPacketTime = millis();
    return true;
}

// Rutina estándar NXP para destrabar el bus I2C si un cable se soltó o hubo ruido
void unwedgeI2CBus() {
    Wire.end();
    pinMode(I2C_SDA, INPUT_PULLUP);
    pinMode(I2C_SCL, OUTPUT_OPEN_DRAIN);
    digitalWrite(I2C_SCL, HIGH);
    delayMicroseconds(10);

    // Enviar 9 pulsos de reloj para que el chip esclavo libere la línea SDA
    for (int i = 0; i < 9; i++) {
        digitalWrite(I2C_SCL, LOW);
        delayMicroseconds(10);
        digitalWrite(I2C_SCL, HIGH);
        delayMicroseconds(10);
    }

    // Generar condición STOP manual
    pinMode(I2C_SDA, OUTPUT_OPEN_DRAIN);
    digitalWrite(I2C_SDA, LOW);
    delayMicroseconds(10);
    digitalWrite(I2C_SCL, HIGH);
    delayMicroseconds(10);
    digitalWrite(I2C_SDA, HIGH);
    delayMicroseconds(10);

    Wire.begin(I2C_SDA, I2C_SCL);
    Wire.setClock(100000); // 100 kHz estándar
    Wire.setTimeOut(40);   // Timeout de 40ms para que nunca se bloquee
    delay(50);
}

bool initBNO08x(uint8_t addr) {
    Serial.printf("Intentando iniciar BNO08x en 0x%02X...\n", addr);
    if (!bno08x.begin_I2C(addr, &Wire)) {
        Serial.println("[BNO08x] Fallo inicializacion; se reintentara.");
        return false;
    }
    delay(100);
    if (bno08x.enableReport(SH2_ROTATION_VECTOR, 20000)) {
        activeReport = SH2_ROTATION_VECTOR;
        Serial.println(" >> Exito: BNO08x activo (SH2_ROTATION_VECTOR a 50Hz).");
        return true;
    }
    if (bno08x.enableReport(SH2_GAME_ROTATION_VECTOR, 20000)) {
        activeReport = SH2_GAME_ROTATION_VECTOR;
        Serial.println(" >> Exito: BNO08x activo (SH2_GAME_ROTATION_VECTOR).");
        return true;
    }
    return false;
}

void scanAndConnect() {
    recoveryCount++;
    Serial.printf("[RECOVERY] Intento %lu\n", recoveryCount);
    detectedSensor = SENSOR_NONE;
    unwedgeI2CBus();

    Serial.println("\n[I2C] Escaneando dispositivos...");
    uint8_t count = 0;
    uint8_t foundAddr = 0;

    for (uint8_t addr = 1; addr < 127; addr++) {
        Wire.beginTransmission(addr);
        if (Wire.endTransmission() == 0) {
            Serial.printf(" [OK] I2C detectado en 0x%02X\n", addr);
            count++;
            if (addr == 0x4A || addr == 0x4B) {
                foundAddr = addr;
                detectedSensor = SENSOR_BNO08X;
                break;
            } else if (addr == 0x28 || addr == 0x29) {
                foundAddr = addr;
                detectedSensor = SENSOR_BNO055;
            }
        }
    }

    if (count == 0) {
        Serial.println(" [!] No responde ningun sensor. Revisa cables/tierra.");
        detectedSensor = SENSOR_NONE;
        return;
    }

    sensorAddr = foundAddr;

    if (detectedSensor == SENSOR_BNO08X) {
        if (initBNO08x(sensorAddr)) {
            lastPacketTime = millis();
            return;
        }
    } else if (detectedSensor == SENSOR_BNO055) {
        bno055 = Adafruit_BNO055(55, sensorAddr, &Wire);
        if (bno055.begin()) {
            bno055.setExtCrystalUse(true);
            detectedSensor = SENSOR_BNO055;
            lastPacketTime = millis();
            Serial.println(" >> Exito: BNO055 activo.");
            return;
        }
    }

    detectedSensor = SENSOR_NONE;
}

void setup() {
    Serial.begin(115200);
    delay(500);

    Serial.println("\n===========================================");
    Serial.println(" ESP32 + BNO Tracker (Auto-Recuperacion)  ");
    Serial.println("===========================================");

    if (SerialBT.begin("ESP32_Tracker")) {
        Serial.println(" [OK] Bluetooth listo: ESP32_Tracker");
    }

    Wire.begin(I2C_SDA, I2C_SCL);
    Wire.setClock(100000);
    Wire.setTimeOut(40);

    scanAndConnect();
}

void loop() {
    unsigned long now = millis();

    // Si no hay sensor conectado o se perdio, reintentar cada 1.5s
    if (detectedSensor == SENSOR_NONE) {
        if (now - lastScanRetry >= 1500) {
            lastScanRetry = now;
            scanAndConnect();
        }
        return;
    }

    // WATCHDOG ANTIFALLOS:
    // Si pasaron mas de 2000ms sin recibir datos (ej: cable flojo momentaneo),
    // destrabar el bus y reiniciar comunicacion automaticamente
    if (now - lastPacketTime > 2000) {
        Serial.println("\n[Watchdog] Silencio detectado (>2000ms). Reconectando sensor...");
        scanAndConnect();
        return;
    }

    if (detectedSensor == SENSOR_BNO08X) {
        if (bno08x.wasReset()) {
            Serial.println("[BNO08x] El sensor reporto reinicio interno, reactivando reporte...");
            if (!bno08x.enableReport(activeReport, 20000)) {
                Serial.println("[BNO08x] No se pudo reactivar reporte.");
            }
        }

        if (bno08x.getSensorEvent(&sensorValue)) {

            if (sensorValue.sensorId == SH2_ROTATION_VECTOR) {
                if (now - lastPrint >= 20) { // 50 Hz
                    lastPrint = now;
                    sendQuaternion(
                        sensorValue.un.rotationVector.real,
                        sensorValue.un.rotationVector.i,
                        sensorValue.un.rotationVector.j,
                        sensorValue.un.rotationVector.k
                    );
                }
            } else if (sensorValue.sensorId == SH2_GAME_ROTATION_VECTOR) {
                if (now - lastPrint >= 20) {
                    lastPrint = now;
                    sendQuaternion(
                        sensorValue.un.gameRotationVector.real,
                        sensorValue.un.gameRotationVector.i,
                        sensorValue.un.gameRotationVector.j,
                        sensorValue.un.gameRotationVector.k
                    );
                }
            }
        }
    } else if (detectedSensor == SENSOR_BNO055) {
        if (now - lastPrint >= 20) {
            lastPrint = now;
            imu::Quaternion quat = bno055.getQuat();
            sendQuaternion(quat.w(), quat.x(), quat.y(), quat.z());
        }
    }
}
