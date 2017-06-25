#!/bin/bash
`which python` manage.py syncdb
`which python` manage.py schemamigration bbb --initial
echo 'updating "SALT" and "BBB_API_URL" in "bbb/local_settings.py"' 

OUTPUT=(`bbb-conf --salt`)
BBB_API_URL=${OUTPUT[1]}
SALT=${OUTPUT[3]}
sed -i "s|SALT = \"\"|SALT=\"${SALT}\"|g" bbb/local_settings.py
sed -i "s|BBB_API_URL = \"\"|BBB_API_URL = \"${BBB_API_URL}\"|g" bbb/local_settings.py
#use manage.py convert_to_south myapp to convert the old app 
