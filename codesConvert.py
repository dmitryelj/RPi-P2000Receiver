print "Started"

text_file = open("capcodes_.txt", "r")
lines = text_file.readlines()
# print lines
print len(lines)
for s in lines:
    fields = s.split('\t')
    if len(fields) >= 5 and ('?' in fields[0]) is False and len(fields[0]) == 9:
        print "{},{}".format(fields[0], fields[4].strip())
text_file.close()

print "Done"
