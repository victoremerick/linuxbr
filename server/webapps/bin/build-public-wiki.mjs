import { cpSync } from 'node:fs';

const source = new URL('../../../packages/linuxbr-system/files/usr/share/linuxbr/wiki/', import.meta.url);
const target = new URL('../public/wiki/', import.meta.url);

cpSync(source, target, { recursive: true });
console.log('Wiki disponível em public/wiki/.');
