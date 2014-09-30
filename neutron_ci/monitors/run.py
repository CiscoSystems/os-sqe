import argparse
import subprocess
import sys
import smtplib
from email.mime.text import MIMEText


def run(args):
    print "Running:", args.cmd

    p = subprocess.Popen([args.cmd] + args.args.split(';'), stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    (out, nothing) = p.communicate()
    print(out.strip())
    if p.returncode and args.emails:
        if not args.smtp_server:
            raise Exception('SMPT server not defined')
        msg = MIMEText(out)
        msg['Subject'] = "Running: {0} {1}".format(args.cmd, args.args)
        msg['From'] = args.from_email
        msg['To'] = args.emails
        s = smtplib.SMTP(host=args.smtp_server, port=25)
        s.sendmail(args.from_email, args.emails, msg.as_string())
        s.quit()
    sys.exit(p.returncode)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help='')

    run_parser = subparsers.add_parser('run', help='Run')
    run_parser.add_argument('--cmd')
    run_parser.add_argument('--args', help='Comma separated list of arguments')
    run_parser.add_argument('--emails', default='')
    run_parser.add_argument('--from-email')
    run_parser.add_argument('--smtp-server', nargs='?')
    run_parser.set_defaults(func=run)
    args = parser.parse_args()
    args.func(args)
