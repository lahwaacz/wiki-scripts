#!/bin/bash

set -eu

if ! [[ -f LocalSettings.php ]]; then
    echo "Running the \`php maintenance/run.php install\` command"

    # run the install script
    # https://www.mediawiki.org/wiki/Manual:Install.php
    php maintenance/run.php install \
        --dbtype="$MW_DB_TYPE" \
        --dbname="$MW_DB_NAME" \
        --dbuser="$MW_DB_USER" \
        --dbpass="$MW_DB_PASSWORD" \
        --dbserver="$MW_DB_HOST" \
        --server="$MW_SERVER" \
        --scriptpath="$MW_SCRIPT_PATH" \
        --lang=en \
        --pass="$MW_PASSWORD" \
        "$MW_NAME" \
        "$MW_USER"

    # add some config settings
    cat >> LocalSettings.php << EOF
\$wgGroupPermissions['*']['createaccount'] = false;
\$wgGroupPermissions['user']['writeapi'] = true;
\$wgGroupPermissions['sysop']['deletelogentry'] = true;
\$wgGroupPermissions['sysop']['deleterevision'] = true;

wfLoadExtension( 'Interwiki' );
\$wgGroupPermissions['sysop']['interwiki'] = true;

# Enable short URLs https://www.mediawiki.org/wiki/Manual:Short_URL/Apache
\$wgScriptPath = "";
\$wgArticlePath = "/wiki/\$1";
\$wgScriptExtension = ".php";
\$wgUsePathInfo = true;

EOF
fi

# execute the default command from the default image
# https://hub.docker.com/_/mediawiki
#exec apache2-foreground
exec /usr/bin/httpd -k start -DFOREGROUND
