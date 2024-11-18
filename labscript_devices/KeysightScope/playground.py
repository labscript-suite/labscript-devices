import pyvisa


rm = pyvisa.ResourceManager()

a = rm.list_resources('USB?*::INSTR')
scope = rm.open_resource(a[0])
print(scope.read('*IDN?'))