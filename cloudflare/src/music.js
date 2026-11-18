import {stripTracking,trim} from './links.js';
// Redirect-only Songlink sharing: no API key, API call or media download.
export function musicLink(raw) {
  try {
    const u=new URL(trim(raw)[0]);
    if(!['http:','https:'].includes(u.protocol)||u.username||u.password||u.port)return null;
    const host=u.hostname.toLowerCase().replace(/^www\./,''),path=u.pathname;
    const supported=['spotify.link','spotify.app.link','dzr.page.link'].includes(host)?/^\/[A-Za-z0-9_-]+\/?$/.test(path):host==='open.spotify.com'?/^\/(?:intl-[a-z-]+\/)?(?:track|album)\/[A-Za-z0-9]+\/?$/.test(path):
      host==='music.apple.com'?/\/(song|album)\//.test(path):
      host==='music.youtube.com'?path==='/watch'&&!!u.searchParams.get('v'):
      ['tidal.com','listen.tidal.com'].includes(host)?/\/(track|album)\/\d+/.test(path):
      host==='deezer.com'?/\/(track|album)\/\d+/.test(path):
      host==='soundcloud.com'?/^\/[^/]+\/[^/]+\/?$/.test(path):
      host==='pandora.com'?/\/(artist|track)\//.test(path):
      host==='music.amazon.com'?/\/(albums|tracks)\//.test(path):false;
    if(!supported)return null;
    const clean=new URL(stripTracking(u.href));clean.protocol='https:';clean.hash='';
    const album=/\/(?:album|albums)\//.test(path)&&!clean.searchParams.has('i');
    const result=`https://${album?'album':'song'}.link/${encodeURIComponent(clean.href)}`;
    return result.length<=2048?result:null;
  }catch{return null;}
}
