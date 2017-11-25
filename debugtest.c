#include <stdio.h>
#include <unistd.h>

// For testing the app without real receiver

int delay_ms = 1000;

int main()
{
  int p;
  for(p=0; p<10; p++) {
      printf("FLEX: 2017-11-20 20:28:33 1600/2/A 07.027 [002029568] ALN A1 12166 Afrit A4 R - Hoofddorp 3 Hoofddorp\r\n");
      fflush(stdout);
      usleep(delay_ms*1000);
      printf("FLEX: 2017-11-20 20:28:57 1600/2/A 07.040 [000726140] ALN A1 MMC SEH Maatweg 3 3813TZ 3 Amersfoort\r\n");
      fflush(stdout);
      usleep(delay_ms*1000);
      printf("FLEX: 2017-11-20 20:29:14 1600/2/A 07.049 [002029568] ALN A1 6525GA 32 Geert Grooteplein Zuid Nijmegen Gezondheid 90522\r\n");
      fflush(stdout);
      usleep(delay_ms*1000);
      printf("FLEX: 2017-11-20 20:29:21 1600/2/A 07.053 [000723083] ALN A1 Laren NH\r\n");
      fflush(stdout);
      usleep(delay_ms*1000);
      printf("FLEX: 2017-11-20 20:29:42 1600/2/A 07.064 [002029568] ALN mnl utr oc: gaarne contact cluster west\r\n");
      fflush(stdout);
      usleep(delay_ms*1000);
      printf("FLEX: 2017-11-20 20:29:46 1600/2/A 07.066 [001123108] ALN A2 5684SB 1 A : Willem de Zwijgerweg Best Obj: gezondheidszorg Bran VWS Post Best Rit: 116021\r\n");
      fflush(stdout);
      usleep(delay_ms*1000);
      printf("FLEX: 2017-11-20 20:30:07 1600/2/A 07.077 [001180000] ALN TESTOPROEP HOOFDSSYSTEEM PGW BN (1)\r\n");
      fflush(stdout);
      usleep(delay_ms*1000);
      printf("FLEX: 2017-11-20 20:30:07 1600/2/A 07.077 [001180000] ALN TESTOPROEP BACK-UP SYSTEEM GMC BN (2)\r\n");
      fflush(stdout);
      usleep(delay_ms*1000);
      printf("FLEX: 2017-11-20 20:30:23 1600/2/A 07.086 [002029568] ALN A1 18172 Hofstee 3284AZ Zuid-Beijerland RITNR 41621\r\n");
      fflush(stdout);
      usleep(delay_ms*1000);
      printf("FLEX: 2017-11-20 20:30:37 1600/2/A 07.093 [002029568] ALN P 2 Buitenbrand Anna Paulownastraat Rotterdam 170631 IC02 Vak: 5991110\r\n");
      fflush(stdout);
      usleep(delay_ms*1000);
      printf("FLEX: 2017-11-20 20:30:52 1600/2/A 07.101 [002029568] ALN 181 indien gereed graag contact ivm vervolgrit\r\n");
      fflush(stdout);
      usleep(delay_ms*1000);
  }
  return 0;
}
