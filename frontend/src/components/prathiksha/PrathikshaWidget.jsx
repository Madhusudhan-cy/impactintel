import React from 'react';
import PrathikshaLauncher from './PrathikshaLauncher';
import PrathikshaChatWindow from './PrathikshaChatWindow';

export default function PrathikshaWidget() {
  return (
    <>
      <PrathikshaChatWindow />
      <PrathikshaLauncher />
    </>
  );
}
