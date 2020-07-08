from machine import ADC, enable_irq, disable_irq

class SystemVoltage():
    """
    Reads the voltage level by sampling the ADC on a pin connected to a voltage divider
    Pycom Extension Board v3.1 is using P16 and 1000 / 1000 as resistors

    Originally written by Dominik Kapusta <https://github.com/ayoy>
    Improved by Andreas Motl <https://github.com/amotl>
    Simplified by Stefan Nilsson to only use Pycom without dependencies
    """
    adc_sample_count = const(100)

    def __init__(self, pin, r1, r2, db):
        assert type(pin) is str, 'VCC Error: Voltage divider ADC pin invalid'
        assert type(r1) is int, 'VCC Error: Voltage divider resistor value "resistor_r1" invalid'
        assert type(r2) is int, 'VCC Error: Voltage divider resistor value "resistor_r2" invalid'
        assert type(db) is float, 'VCC Error: ADC attenuation value "adc_attenuation_db" invalid'

        self.pin = pin
        self.resistor_r1 = r1
        self.resistor_r2 = r2
        
        if db == 0.0:
            self.adc_atten = ADC.ATTN_0DB
        elif db == 2.5:
            self.adc_atten = ADC.ATTN_2_5DB
        elif db == 6.0:
            self.adc_atten = ADC.ATTN_6DB
        elif db == 11.0:
            self.adc_atten = ADC.ATTN_11DB
        else:
            raise ValueError('ADC attenuation value (adc_attenuation_db) not allowed : {}'.format(db))

        self.adc = ADC(id=0)

    def read(self):
        adc_samples = [0.0] * self.adc_sample_count
        adc_mean = 0.0
        i = 0

        self.adc.init()
        adc_channel = self.adc.channel(attn=self.adc_atten, pin=self.pin)
        irq_state = disable_irq()
        while i < self.adc_sample_count:
            sample = adc_channel()
            adc_samples[i] = sample
            adc_mean += sample
            i += 1
        enable_irq(irq_state)

        adc_mean /= self.adc_sample_count
        adc_variance = 0.0
        for sample in adc_samples:
            adc_variance += (sample - adc_mean) ** 2
        adc_variance /= (self.adc_sample_count - 1)

        raw_voltage = adc_channel.value_to_voltage(4095)
        mean_voltage = adc_channel.value_to_voltage(int(adc_mean))

        mean_variance = (adc_variance * 10 ** 6) // (adc_mean ** 2)

        # print("ADC readings. count=%u:\n%s" %(self.adc_sample_count, str(adc_samples)))
        # print("SystemVoltage: Mean of ADC readings (0-4095) = %15.13f" % adc_mean)
        # print("SystemVoltage: Mean of ADC voltage readings (0-%dmV) = %15.13f" % (raw_voltage, mean_voltage))
        # print("SystemVoltage: Variance of ADC readings = %15.13f" % adc_variance)
        # print("SystemVoltage: 10**6*Variance/(Mean**2) of ADC readings = %15.13f" % mean_variance)

        resistor_sum = self.resistor_r1 + self.resistor_r2
        voltage_millivolt = (adc_channel.value_to_voltage(int(adc_mean))) * resistor_sum / self.resistor_r2
        voltage_volt = voltage_millivolt / 1000.0
        
        # Shut down ADC channel.
        adc_channel.deinit()

        # return adc_mean
        return voltage_volt

    def power_off(self):
        # Shut down ADC
        self.adc.deinit()