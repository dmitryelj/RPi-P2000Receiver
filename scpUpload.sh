name="pi"
password="raspberry"

rpi=$name"@192.168.0.124"
rpiPath=$rpi":/home/"$name"/Documents/P2000"

echo "Upload files to "$rpiPath
sshpass -p $password scp *.py $rpiPath
sshpass -p $password scp *.c $rpiPath
sshpass -p $password scp *.txt $rpiPath

echo "Done"
