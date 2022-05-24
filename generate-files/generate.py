import xlrd
from jinja2 import Environment, FileSystemLoader
from collections import OrderedDict
import os
import shutil
import re

FNAME = 'motors.xlsx'

def get_motor_types(workbook):
    ws = workbook.sheet_by_name('Motor Types')
    header = [h for h in ws.row_values(0)]

    types = {}

    for row_num in range(1, ws.nrows):
        row = dict(zip(header, ws.row_values(row_num)))
        types[row['Motor Type']] = int(row['IOC Setting'])

    return types

def get_encoder_types(workbook):
    ws = workbook.sheet_by_name('Encoder Types')
    header = [h for h in ws.row_values(0)]

    types = {}

    for row_num in range(1, ws.nrows):
        row = dict(zip(header, ws.row_values(row_num)))
        types[row['Encoder Type']] = int(row['IOC Setting'])

    return types

def get_vector(workbook):
    ws = workbook.sheet_by_name('Vector')

    header = [h for h in ws.row_values(0)]

    # All controllers defined in the worksheet
    controllers = OrderedDict()

    # Current controller being parsed
    controller = None
    P = None
    R = None

    for row_num in range(1, ws.nrows):
        row = dict(zip(header, ws.row_values(row_num)))

        axis = row['Axis']

        # Skip over empty lines
        if not axis:
            continue

        # Check if we found a new controller
        if row['Loc']:
            P = row['P']
            R = row['R']

            # Add
            num = int(row['Controller'])
            controller = controllers[num] = {
                'Num': num,
                'Vector': {
                    'P': row['P'],
                    'R': row['R'],
                    'AX': OrderedDict(),
                }
            }

        controller['Vector']['AX'][axis] = {
            'IDX':  int(row['Index']),
            'AX':   axis,
            'EGU':  row['EGU']
        }

    return controllers

def get_temperatures(workbook):
    ws = workbook.sheet_by_name('Temperatures')

    header = [h for h in ws.row_values(0)]

    # All controllers defined in the worksheet
    controllers = OrderedDict()

    # Current controller being parsed
    controller = None

    for row_num in range(1, ws.nrows):
        row = dict(zip(header, ws.row_values(row_num)))

        prefix = row['Motor']

        # Skip over empty lines
        if not prefix:
            continue

        # Check if we found a new controller
        if row['Loc']:
            # Add
            num = int(row['Controller'])
            controller = controllers[num] = {
                'Num': num,
                'Temperatures': OrderedDict()
            }

        ai   = int(row['Analog Input'])

        controller['Temperatures'][prefix] = {
            'P':    prefix,
            'R':    f'GalilAi{ai}',
            'ADDR': ai + 1,
            'CALC': row['Formula'],
            'EGU':  row['EGU'],
            'PREC': int(row['PREC']),
        }

    return controllers

def get_digital_outputs(workbook):
    ws = workbook.sheet_by_name('Digital Outputs')

    header = [h for h in ws.row_values(0)]

    # All controllers defined in the worksheet
    controllers = OrderedDict()

    # Current controller being parsed
    controller = None

    for row_num in range(1, ws.nrows):
        row = dict(zip(header, ws.row_values(row_num)))

        name = row['Name']

        # Skip over empty lines
        if not name:
            continue

        # Check if we found a new controller
        if row['Loc']:
            # Add
            num = int(row['Controller'])
            controller = controllers[num] = {
                'Num': num,
                'Digital Outputs': OrderedDict()
            }

        do = int(row['Digital Output'])

        controller['Digital Outputs'][name] = {
            'R':    name,
            'WORD': 0,
            'MASK': f'0x{1 << (do-1):4x}',
            'ZNAM': row['ZNAM'],
            'ONAM': row['ONAM'],
        }

    return controllers

def get_controllers(workbook):
    motor_types     = get_motor_types(workbook)
    encoder_types   = get_encoder_types(workbook)
    vector          = get_vector(workbook)
    temperatures    = get_temperatures(workbook)
    digital_outputs = get_digital_outputs(workbook)

    ws = workbook.sheet_by_name('Motors')

    header = [h for h in ws.row_values(0)]

    # All controllers defined in the worksheet
    controllers = OrderedDict()

    # Parsing this controller, currently
    controller = None

    # Iterate over all rows past the first (first row is header)
    for row_num in range(1, ws.nrows):
        # Row as dictionary
        row = dict(zip(header, ws.row_values(row_num)))

        # Axis name
        name = row['Name'].strip()

        # Skip over empty axes
        if not name:
            continue

        # Check if we found a new controller
        if row['Loc']:
            # Add
            num = int(row['Controller'])
            controller = controllers[num] = {
                'Num':  num,
                # Use same Sys as the one for the first axis
                'P':    f"{row['Sys']}{{Galil:{num}}}",
                'IP':   row['IP'].strip(),
                'Axes': OrderedDict(),

                # Slit blades (temporary dict)
                'Blades': OrderedDict(),

                # Slit pairs, built from 'Blades'
                'Slits': [],

                # Unused CS Motors
                'CS Motors': iter('IJKLMNOP')
            }

        # Read fields of interest
        def maybe_empty(name, default_val):
            val = row[name]
            if not val:
                return default_val
            return val

        vel             = maybe_empty('Vel (units/sec)', 10.0)
        accel           = maybe_empty('Accel (msec to vel)', 100)/1000.0
        usteps_per_step = maybe_empty('uSteps/step', 1)
        steps_per_rev   = int(row['Steps/rev']*usteps_per_step)
        gear_ratio      = maybe_empty('Gear Ratio (1:x)', 1)
        pitch           = maybe_empty('Pitch (units/rev)', 1)
        eres            = maybe_empty('Encoder (cts/unit)', 0)
        bdst            = maybe_empty('Backlash (units)', 0.0)
        if eres:
            eres = 1.0 / eres

        # One revolution of the motor is equivalent to this stage motion, in EGU
        motor_res_calc  = 1 / (steps_per_rev*gear_ratio*pitch)
        motor_res_given = maybe_empty('Motor Res (steps/unit)', 0)
        motor_res       = (1 / motor_res_given) if motor_res_given else motor_res_calc

        closed_loop     = maybe_empty('Closed Loop?', 'No').strip() == 'Yes'
        ueip            = 1 if closed_loop else 0
        motor_res       = eres if closed_loop and eres else motor_res

        enc1_type       = encoder_types.get(row['Encoder Type'], 0)
        enc2_type       = encoder_types.get(row['2nd Encoder Type'], 0)

        # Auto On?
        auto_on_off     = maybe_empty('Auto On?', 'No') == 'Yes'

        # Should the motion be reversed in EPICS?
        reversed        = maybe_empty('Reversed?', 'No') == 'Yes'

        # Limits as Home?
        limits_as_home  = maybe_empty('Limits as Home', 'Yes') == 'Yes'

        # To which direction (after reversal) should homing be done?
        home_direction  = maybe_empty('Home to Limit', 'Positive')
        assert home_direction in ('Positive', 'Negative')

        home_allowed, home_dir = {
            (False, 'Negative'): (1, 'R'),
            (False, 'Positive'): (2, 'F'),
            (True,  'Negative'): (2, 'F'),
            (True,  'Positive'): (1, 'R'),
        }[(reversed, home_direction)]
        off             = maybe_empty('Pos at Home (units)', 0.0)

        # Soft limits
        dhlm            = maybe_empty('Upper Lim (units)', 0.0) + off
        dllm            = maybe_empty('Lower Lim (units)', 0.0) + off

        controller['Axes'][name] = axis = {
            'Axis':     row['Axis'],
            'P':        row['Sys'] + row['Dev'],
            'ADDR':     'ABCDEFGH'.index(row['Axis']),
            'DESC':     name,
            'EGU':      row['Units'],
            'OFF':      off,
            'MRES':     motor_res,
            'SREV':     steps_per_rev,
            'ERES':     eres,
            'PREC':     int(row['Precision']),
            'VELO':     vel,
            'VMAX':     vel,
            'ACCL':     accel,
            'UEIP':     ueip,
            'DIR':      int(reversed),
            # Limits
            'DHLM':     dhlm,
            'DLLM':     dllm,
            # Backlash distance
            'BDST':     bdst,
            # Extras
            'MTRTYPE':  motor_types[row['Motor Type']],
            'MTRON':    0,
            'ENC1TYPE': enc1_type,
            'ENC2TYPE': enc2_type,
            'HOMEALLOWED': home_allowed,
            'AUTOONOFF':   int(auto_on_off),
            'HOMEDIR':  home_dir,
            'LIMITSASHOME': int(limits_as_home),
        }

        # Check if axis belongs to a slit pair
        blade = row['Slits?']
        if blade:
            name, pos = blade[:-1], blade[-1:]
            assert pos in '+-'

            blades = controller['Blades']

            if name not in blades:
                # Store blade for later
                blades[name] = { pos: axis['Axis'] }
            else:
                # Found the second blade for this pair
                assert pos not in blades[name]
                pair = blades.pop(name)
                pair[pos] = axis['Axis']

                # Figure out motors participating in coordinated motion
                gap_mtr = next(controller['CS Motors'])
                ctr_mtr = next(controller['CS Motors'])

                minus_mtr, plus_mtr = pair['-'], pair['+']

                # Generate forward and reverse kinematic equations
                gap_fwd   = f'{gap_mtr}={plus_mtr}-{minus_mtr}'
                ctr_fwd   = f'{ctr_mtr}=({plus_mtr}+{minus_mtr})/2'
                minus_rev = f'{minus_mtr}={ctr_mtr}-{gap_mtr}/2'
                plus_rev  = f'{plus_mtr}={ctr_mtr}+{gap_mtr}/2'

                gap_fwd   = f'{plus_mtr}-{minus_mtr}'
                ctr_fwd   = f'({plus_mtr}+{minus_mtr})/2'
                minus_rev = f'{ctr_mtr}-{gap_mtr}/2'
                plus_rev  = f'{ctr_mtr}+{gap_mtr}/2'

                desc      = axis['DESC'].split()[:-1]    # Axis description without last word
                gap_desc  = ' '.join(desc + [name, 'Gap'])
                ctr_desc  = ' '.join(desc + [name, 'Center'])

                p_re      = r'-Ax:[^}]+}'
                gap_p     = re.sub(p_re, f'-Ax:{name}Gap}}', axis['P'])
                ctr_p     = re.sub(p_re, f'-Ax:{name}Ctr}}', axis['P'])

                gap = dict(axis)
                ctr = dict(axis)

                gap.update({
                    'Axis': gap_mtr,
                    'P': gap_p,
                    'DESC': gap_desc,
                    'ADDR': 'IJKLMNOPQ'.index(gap_mtr) + 8,
                    'FWD': gap_fwd,
                    'REV': {
                        minus_mtr: minus_rev,
                        plus_mtr: plus_rev,
                    },
                    'OFF': 0.0,
                    'DIR': 0,
                })

                ctr.update({
                    'Axis': ctr_mtr,
                    'P': ctr_p,
                    'DESC': ctr_desc,
                    'ADDR': 'IJKLMNOPQ'.index(ctr_mtr) + 8,
                    'FWD': ctr_fwd,
                    'REV': {
                        minus_mtr: minus_rev,
                        plus_mtr: plus_rev,
                    },
                    'OFF': 0.0,
                    'DIR': 0,
                })
                controller['Slits'] += [gap, ctr]

    # Add vector specification:
    for cnum, c in controllers.items():
        if cnum in vector:
            c['Vector'] = vector[cnum]['Vector']

    # Add temperature reading specifications (only to controllers that have motors)
    for cnum, c in controllers.items():
        if cnum in temperatures:
            c['Temperatures'] = temperatures[cnum]['Temperatures']

    # Add digital output specifications (only to controllers that have motors)
    for cnum, c in controllers.items():
        if cnum in digital_outputs:
            c['Digital Outputs'] = digital_outputs[cnum]['Digital Outputs']

    return controllers

if __name__ == '__main__':

    # Formatters
    def fmt(value, width, just, quote, last=False):
        assert just in 'rl'

        # Add quotes and left space
        if quote:
            value = f' "{value}"'
        else:
            value = f' {value}'

        # Add comma and right space
        if last:
            value = f'{value} '
        else:
            value = f'{value}, '

        # Justify
        if just == 'r':
            return value.rjust(width)
        else:
            return value.ljust(width)

    # Field header
    def hdr(value, width, just, last=False):
        return fmt(value, width, just, False, last)

    # Field with string value
    def sfld(value, width, just, last=False):
        return fmt(value, width, just, True, last)

    # Field with floating point value
    def ffld(value, prec, width, just, last=False):
        value = f'{value:.0{prec}f}'
        return fmt(value, width, just, True, last)

    # Field witl exponential-notation value
    def efld(value, prec, width, just, last=False):
        value = f'{value:.0{prec}e}'
        return fmt(value, width, just, True, last)

    env = Environment(loader=FileSystemLoader('./'))
    env.filters['hdr']  = hdr
    env.filters['sfld'] = sfld
    env.filters['ffld'] = ffld
    env.filters['efld'] = efld

    wb = xlrd.open_workbook(FNAME)
    controllers = get_controllers(wb)

    for cnum, c in controllers.items():
        print(f'Galil #{cnum}:')
        for a in c['Axes'].values():
            print(f"  {a['Axis']}: {a['DESC']}")

        data = dict(
            controller=c,
            axes=c['Axes'],
            slits=c['Slits'],
            vec=c.get('Vector', {}),
            temps=c.get('Temperatures', {}),
            dig_outs=c.get('Digital Outputs', {}),
        )

        # Write substitutions file
        subs_file = f'../galilApp/Db/galil{cnum}.substitutions'
        with open(subs_file, 'wb') as f:
            f.write(env.get_template('galil.substitutions.j2').render(**data).encode())

        # Write startup script
        st_folder = f'../iocBoot/ioc-galil{cnum}'
        try:
            os.mkdir(st_folder)
            shutil.copy('Makefile', st_folder)
        except FileExistsError:
            pass

        st_file = f'{st_folder}/st.cmd'
        with open(st_file, 'wb') as f:
            f.write(env.get_template('st.cmd.j2').render(**data).encode())

        # Make startup script executable
        os.chmod(st_file, 0o755)

        # Autosave settings
        settings_file = f'{st_folder}/galil_settings.req'
        with open(settings_file, 'wb') as f:
            f.write(env.get_template('galil_settings.req.j2').render(**data).encode())

        # Autosave positions
        positions_file = f'{st_folder}/galil_positions.req'
        with open(positions_file, 'wb') as f:
            f.write(env.get_template('galil_positions.req.j2').render(**data).encode())

        print(f'Galil #{cnum} Done\n')


