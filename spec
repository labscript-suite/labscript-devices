- worker classes - provide function to look up based on BLACS tab instance:
    - enforce that there must be a worker defined

- all classes - provide function to look up based on module name / labscript class name (identical)

- labscript class decorator: enforce module name must equal class name

- other class decorators: add classes to lookup dictionary in labscipt_devices
