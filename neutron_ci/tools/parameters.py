# Copyright 2014 Cisco Systems, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
# @author: Nikolay Fedotov, Cisco Systems, Inc.

import sys
import argparse
import time
from sqlalchemy import create_engine, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, UnicodeText, Boolean, TIMESTAMP
from sqlalchemy.orm import sessionmaker


DEFAULT_CONNECTION = 'mysql://root:root@localhost/neutron'

Base = declarative_base()
Session = sessionmaker()


class Parameters(Base):
    __tablename__ = 'parameters'

    id = Column(Integer, primary_key=True)
    text = Column(UnicodeText)
    blocked = Column(Boolean, default=False)
    timestamp = Column(TIMESTAMP, server_default=func.now(),
                       onupdate=func.current_timestamp())


def sync_db(args):
    Base.metadata.create_all(engine)


def add_parameters(args):
    session = Session()
    try:
        text = args.file.read()
        parameters = Parameters(text=unicode(text))
        session.add(parameters)
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()


def allocate(args):
    looking = True
    while looking:
        session = Session()
        try:
            param = session.query(Parameters).filter(
                Parameters.blocked==False).order_by(
                Parameters.timestamp).first()
            if not param:
                print('# There are not free parameters')
                if args.wait:
                    print('# Sleep for {t} seconds'
                          ''.format(t=args.sleep_time))
                    time.sleep(args.sleep_time)
                else:
                    looking = False
            else:
                param.blocked = True
                session.commit()
                print('export PARAM_ID={id}'.format(id=param.id))
                print(param.text)
                looking = False
        except:
            session.rollback()
            raise
        finally:
            session.close()


def release(args):
    session = Session()
    try:
        param = session.query(Parameters).get(args.id)
        if not param:
            raise Exception('Not found')
        param.blocked = False
        session.commit()
        print('Released')
    except:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help='')

    syncdb_parser = subparsers.add_parser('syncdb', help='Sync DB')
    syncdb_parser.set_defaults(func=sync_db)
    syncdb_parser.add_argument('--connection', nargs='?',
                               default=DEFAULT_CONNECTION)

    add_parser = subparsers.add_parser('add', help='Add parameters')
    add_parser.add_argument('--file', nargs='?', type=argparse.FileType('r'),
                            default=sys.stdin)
    add_parser.add_argument('--connection', nargs='?',
                            default=DEFAULT_CONNECTION)
    add_parser.set_defaults(func=add_parameters)

    allocated_parser = subparsers.add_parser('allocate',
                                             help='Allocate parameters')
    allocated_parser.add_argument('--connection', nargs='?',
                                  default=DEFAULT_CONNECTION)
    allocated_parser.add_argument('--wait', action='store_true')
    allocated_parser.add_argument('--sleep-time', nargs='?', default=30)
    allocated_parser.set_defaults(func=allocate)

    release_parser = subparsers.add_parser('release',
                                           help='Release parameters')
    release_parser.add_argument('--id')
    release_parser.add_argument('--connection', nargs='?',
                                default=DEFAULT_CONNECTION)
    release_parser.set_defaults(func=release)
    args = parser.parse_args()

    engine = create_engine(args.connection)
    Session.configure(bind=engine)
    args.func(args)
