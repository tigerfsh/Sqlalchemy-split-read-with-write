#!/bin/bash

docker-compose down
rm -rf ./master/data/*
rm -rf ./slave_0/data/*
rm -rf ./slave_1/data/*
docker-compose build
docker-compose up -d

until docker exec master sh -c 'export MYSQL_PWD=111; mysql -u root -e ";"'
do
    echo "Waiting for master database connection..."
    sleep 4
done

priv_stmt='GRANT ALL  ON *.* TO "mydb_slave_user"@"%" IDENTIFIED BY "mydb_slave_pwd"; FLUSH PRIVILEGES;'
docker exec master sh -c "export MYSQL_PWD=111; mysql -u root -e '$priv_stmt'"

until docker-compose exec slave_0 sh -c 'export MYSQL_PWD=111; mysql -u root -e ";"'
do
    echo "Waiting for slave_0 database connection..."
    sleep 4
done

until docker-compose exec slave_1 sh -c 'export MYSQL_PWD=111; mysql -u root -e ";"'
do
    echo "Waiting for slave_1 database connection..."
    sleep 4
done

docker-ip() {
    docker inspect --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$@"
}

MS_STATUS=`docker exec master sh -c 'export MYSQL_PWD=111; mysql -u root -e "SHOW MASTER STATUS"'`
CURRENT_LOG=`echo $MS_STATUS | awk '{print $6}'`
CURRENT_POS=`echo $MS_STATUS | awk '{print $7}'`

start_slave_stmt="CHANGE MASTER TO MASTER_HOST='$(docker-ip master)',MASTER_USER='mydb_slave_user',MASTER_PASSWORD='mydb_slave_pwd',MASTER_LOG_FILE='$CURRENT_LOG',MASTER_LOG_POS=$CURRENT_POS; START SLAVE;"
start_slave_cmd='export MYSQL_PWD=111; mysql -u root -e "'
start_slave_cmd+="$start_slave_stmt"
start_slave_cmd+='"'

docker exec slave_0 sh -c "$start_slave_cmd"
docker exec slave_0 sh -c "export MYSQL_PWD=111; mysql -u root -e 'SHOW SLAVE STATUS \G'"


docker exec slave_1 sh -c "$start_slave_cmd"
docker exec slave_1 sh -c "export MYSQL_PWD=111; mysql -u root -e 'SHOW SLAVE STATUS \G'"

priv_stmt_short='GRANT ALL  ON *.* TO "mydb_slave_user"@"%"; FLUSH PRIVILEGES;'
docker exec slave_0 sh -c "export MYSQL_PWD=111; mysql -u root -e '$priv_stmt_short'"
docker exec slave_1 sh -c "export MYSQL_PWD=111; mysql -u root -e '$priv_stmt_short'"

