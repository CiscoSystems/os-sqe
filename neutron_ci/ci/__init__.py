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
# @author: Dane LeBlanc, Nikolay Fedotov, Cisco Systems, Inc.

import os
import logging
import logging.handlers

logger = logging.getLogger()
formatter = logging.Formatter('%(asctime)s %(name)s: %(lineno)d, '
                              '%(levelname)s: %(message)s')

# Add console log handler
CONSOLE_LOG_LEVEL = int(os.environ.get('CONSOLE_LOG_LEVEL', logging.INFO))
console_handler = logging.StreamHandler()
console_handler.setLevel(CONSOLE_LOG_LEVEL)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Handler for console.txt
info_file_handler = logging.FileHandler('console.txt')
info_file_handler.setLevel(logging.INFO)
info_file_handler.setFormatter(formatter)
logger.addHandler(info_file_handler)
