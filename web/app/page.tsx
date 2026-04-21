import {HomeClient} from '../components/HomeClient';
import {getLatestDeals, getStatusSnapshot} from '../lib/data';

export default function Home() {
  const status = getStatusSnapshot();

  return <HomeClient initialDeals={getLatestDeals()} updatedAt={status.latestDealsUpdatedAt} />;
}
