#####################################################################
#                                                                   #
# /NI_DAQmx/models/generate_classes.py                              #
#                                                                   #
# Copyright 2018, Christopher Billington                            #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################
import os
import warnings
import json
from string import Template

from labscript_utils import dedent

THIS_FOLDER = os.path.dirname(os.path.abspath(__file__))
CAPABILITIES_FILE = os.path.join(THIS_FOLDER, 'capabilities.json')
TEMPLATE_FILE = os.path.join(THIS_FOLDER, '_subclass_template.py')


def reformat_files(filepaths):
    """Apply black formatter to a list of source files"""
    try:
        import black
    except ImportError:
        msg = """Cannot import code formatting library 'black'. Generated labscript
            device code may be poorly formatted. Install black (Python 3.6+ only) via
            pip and run again to produce better formatted files"""
        warnings.warn(dedent(msg))
        return

    from click.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(black.main, ["-S"] + filepaths)
    print(result.output)
    assert result.exit_code == 0, result.output


def main():
    capabilities = {}
    if os.path.exists(CAPABILITIES_FILE):
        with open(CAPABILITIES_FILE) as f:
            capabilities = json.load(f)

    with open(TEMPLATE_FILE) as f:
        template = Template(f.read())

    autogeneration_warning = """\
    #####################################################################
    #     WARNING                                                       #
    #                                                                   #
    # This file is auto-generated, any modifications may be             #
    # overwritten. See README.txt in this folder for details            #
    #                                                                   #
    #####################################################################
    """

    filepaths = []
    for model, device_capabilities in capabilities.items():
        model_name = 'NI-' + model
        class_name = model_name.replace('-', '_')
        filepath = os.path.join(THIS_FOLDER, class_name + '.py')
        src = template.substitute(
            AUTOGENERATION_WARNING=autogeneration_warning,
            CAPABILITIES=device_capabilities,
            CLASS_NAME=class_name,
            MODEL_NAME=model_name,
        )
        with open(filepath, 'w', newline='\n') as f:
            f.write(src)
        filepaths.append(filepath)
        print('generated %s' % os.path.basename(filepath))

    if filepaths:
        reformat_files(filepaths)

if __name__ == '__main__':
    main()