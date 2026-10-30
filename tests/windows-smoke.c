/* Compile twice with MinGW; test actual Windows file APIs through Wine. */
#include <windows.h>
#include <stdio.h>

int main(void) {
    const char *name=sizeof(void*)==8 ? "linuxbr-windows-64-ok.txt" : "linuxbr-windows-32-ok.txt";
    HANDLE file=CreateFileA(name,GENERIC_WRITE,0,NULL,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE)return 2;
    const char text[]="Linux BR: programa Windows executado com sucesso via Wine.\r\n";
    DWORD written=0;
    BOOL ok=WriteFile(file,text,sizeof(text)-1,&written,NULL);
    CloseHandle(file);
    if(!ok || written!=sizeof(text)-1)return 3;
    printf("WINDOWS_API_OK bits=%u\n",(unsigned)(sizeof(void*)*8));
    return 0;
}
