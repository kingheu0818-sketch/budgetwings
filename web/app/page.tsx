import {HomeClient} from '../components/HomeClient';
import {getLatestDeals} from '../lib/data';

export default function Home() {
  return <HomeClient initialDeals={getLatestDeals()} />;
}
